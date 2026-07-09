# -*- coding: utf-8 -*-
import json
import re
from datetime import timedelta
from odoo.tools import html2plaintext
from odoo import models, fields, api, _
from odoo.exceptions import AccessError
from odoo.modules.module import get_manifest

WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"]


class FiqControlRoomConfig(models.Model):
    """Per-user/per-company setup for the Control room (FIQ's own governance layer
    on top of res.groups): level + which widgets are shown. Governed by access groups
    + record rules (a user only sees their own)."""
    _name = "fiq.gui.control.config"
    _description = "FIQ Control room – user setup"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users", string="User", required=True, index=True, ondelete="cascade",
        default=lambda s: s.env.user,
    )
    company_id = fields.Many2one(
        "res.company", string="Company", required=True, index=True,
        default=lambda s: s.env.company,
    )
    level = fields.Selection(
        [("pulse", "Pulse (summary)"), ("balansert", "Balanced"), ("detaljert", "Detailed")],
        string="Detail level", default="balansert", required=True,
        help="Role-based detail level: Pulse (executive) · Balanced (project manager) · Detailed (power).",
    )
    show_kpis = fields.Boolean("KPI row", default=True)
    show_projects = fields.Boolean("Project overview", default=True)
    show_kommunikasjon = fields.Boolean("Communication", default=True)
    show_activity = fields.Boolean("Activity", default=True)
    show_tasks = fields.Boolean("Tasks", default=True)
    show_chart = fields.Boolean("Progress chart", default=True)
    show_copilot = fields.Boolean("AI Copilot", default=True)
    show_quick = fields.Boolean("Quick actions", default=True)
    # 📌 Rekkefølge på flatens blokker (komma-liste; per bruker, følger på tvers av maskiner)
    widget_order = fields.Char("Block order", default="")

    # Odoo 19: use models.Constraint (not the deprecated _sql_constraints)
    _user_company_uniq = models.Constraint(
        "unique(user_id, company_id)",
        "One Control room setup per user per company.",
    )

    def _get_or_create_current(self):
        rec = self.search(
            [("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)], limit=1
        )
        if not rec:
            rec = self.create({})
        return rec

    @api.model
    def get_my_config(self):
        rec = self._get_or_create_current()
        comp = self.env.company
        logo = comp.fiq_control_logo
        if logo:
            logo = logo.decode() if isinstance(logo, bytes) else logo
        # Companies the user may switch to (company picker)
        companies = [{"id": c.id, "name": c.name} for c in self.env.user.company_ids]
        # Config-drevet per-linje fremdrift (lag 2): form (bar/ring) + metrikk. Fornuftige
        # defaults, overstyrbare via system-parametere (Innstillinger → Teknisk → Parametere).
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "id": rec.id,
            "level": rec.level,
            "show": {w: bool(rec["show_" + w]) for w in WIDGETS},
            "is_admin": self.env.user.has_group("fiq_gui_control.group_admin"),
            # Company/branding resolved server-side (no dependency on the company service in OWL)
            "company_name": comp.name or "",
            "company_id": comp.id,
            "companies": companies,
            "accent": comp.fiq_control_accent or "#38B44A",
            "logo": ("data:image/png;base64,%s" % logo) if logo else False,
            "progress_shape": ICP.get_param("fiq_gui_control.progress_shape", "bar"),
            "progress_metric": ICP.get_param("fiq_gui_control.progress_metric", "timer"),
            # Versjon: installert (DB, endres av «Oppgrader» i Apper) + filene på disk.
            # Avvik → GUI-et varsler «trykk Oppgrader» (fanger filer-nyere-enn-DB-fella).
            "version_installed": self._module_versions()[0],
            "version_files": self._module_versions()[1],
            # Auto-oppdatering: intervall i minutter (config-drevet, overstyrbar)
            "auto_refresh_min": int(ICP.get_param("fiq_gui_control.auto_refresh_min", "5") or 5),
            # Hvem kan kjøre modul-oppgradering fra brikken (FIQ-admin ELLER Settings-admin)
            "can_upgrade": (self.env.user.has_group("fiq_gui_control.group_admin")
                            or self.env.user.has_group("base.group_system")),
            # SP-lenker per fagområde (config-drevet, PER FIRMA): systemparameter
            # fiq_gui_control.sp_urls.<company_id> (fallback .sp_urls) = JSON {"1": "https://…", "8.50": "https://…"}
            "sp_urls": self._sp_urls(comp),
            # AI-cockpit (Artifact, interim til full Odoo-bygging): config-drevet URL
            "ai_cockpit_url": ICP.get_param("fiq_gui_control.ai_cockpit_url", ""),
            # 📌 Blokk-rekkefølge på flaten (per bruker)
            "widget_order": rec.widget_order or "",
        }

    @api.model
    def set_widget_order(self, order):
        """📌 Lagre brukerens blokk-rekkefølge (komma-liste av blokknøkler)."""
        self._get_or_create_current().write({"widget_order": order or ""})
        return True

    @api.model
    def post_note(self, model, res_id, text):
        """📝 Fritekst-notat fra Kontrollrommet (PC + mobil): logges i chatter som internt notat."""
        text = (text or "").strip()
        if not text or model not in ("project.task", "project.project"):
            return False
        rec = self.env[model].browse(int(res_id)).exists()
        if not rec:
            return False
        rec.message_post(body=text, subtype_xmlid="mail.mt_note")
        return True

    @api.model
    def get_puls(self):
        """⚡ Puls (AI KTRL): dine åpne oppgaver med frist i dag / denne uken — ALLE prosjekter."""
        out = {"idag": [], "uke": []}
        try:
            T = self.env["project.task"]
            f = T._fields
            today = fields.Date.context_today(self)
            week_end = today + timedelta(days=6 - today.weekday())
            for t in T.search([("user_ids", "in", [self.env.uid]),
                               ("date_deadline", "!=", False)],
                              order="date_deadline", limit=120):
                if self._stage_is_done(t.stage_id if "stage_id" in f else False):
                    continue
                d = fields.Date.to_date(str(t.date_deadline)[:10])
                if d > week_end:
                    break
                row = {"id": t.id, "no": (t.code if "code" in f else "") or "",
                       "name": t.name or "", "frist": str(d),
                       "prosjekt": t.project_id.name or "", "over": d < today}
                (out["idag"] if d <= today else out["uke"]).append(row)
            out["idag"], out["uke"] = out["idag"][:15], out["uke"][:15]
        except Exception:
            pass
        return out

    @api.model
    def get_recent_projects(self, n=5, root_id=False):
        """📌 De N siste prosjektene med AKTIVITET (oppgave-endringer), evt. innenfor låst gruppering."""
        n = max(1, min(int(n or 5), 12))
        dom = [("project_id.active", "=", True)]
        if root_id:
            dom.append(("project_id", "child_of", int(root_id)))
        out, seen = [], set()
        for t in self.env["project.task"].search(dom, order="write_date desc", limit=400):
            p = t.project_id
            if not p or p.id in seen:
                continue
            seen.add(p.id)
            if "is_template" in p._fields and p.is_template:
                continue
            no = p.sequence_code if "sequence_code" in p._fields else ""
            out.append({"id": p.id, "name": p.name, "no": no or ""})
            if len(out) >= n:
                break
        return out

    @api.model
    def _sp_urls(self, comp):
        ICP = self.env["ir.config_parameter"].sudo()
        raw = ICP.get_param("fiq_gui_control.sp_urls.%s" % comp.id) \
            or ICP.get_param("fiq_gui_control.sp_urls", "{}")
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @api.model
    def _module_versions(self):
        """(installert DB-versjon, fil-versjon) for fiq_gui_control — defensivt."""
        installed = files = ""
        try:
            mod = self.env["ir.module.module"].sudo().search(
                [("name", "=", "fiq_gui_control")], limit=1)
            installed = mod.latest_version or ""
        except Exception:
            pass
        try:
            files = (get_manifest("fiq_gui_control") or {}).get("version", "")
        except Exception:
            pass
        return installed, files

    @api.model
    def set_widget(self, widget, value):
        if widget in WIDGETS:
            self._get_or_create_current().write({"show_" + widget: bool(value)})
        return True

    @api.model
    def get_ai_stages(self):
        """AI-merkede oppgave-stadier (fiq_ai_stage=True) – unike navn. Brukes til å
        markere/prioritere AI-stadiene i stadie-velgeren. Defensiv: tomt hvis feltet
        ikke finnes ennå (modulen ikke oppgradert)."""
        Stage = self.env["project.task.type"]
        if "fiq_ai_stage" not in Stage._fields:
            return []
        seen, out = set(), []
        for s in Stage.search([("fiq_ai_stage", "=", True)], order="sequence, id"):
            nm = s.name or ""
            if nm and nm not in seen:
                seen.add(nm)
                out.append(nm)
        return out

    # ---- Config-drevet per-linje fremdrift (lag 2) ---------------------------
    # STANDARD = timebasert: førte timer (effective_hours) ÷ estimerte/antatte timer
    # (allocated_hours). Estimatet er redigerbart i Kontrollrommet. Portabelt
    # (felt-guard via _fields) + defensivt. Returnerer {id: {"pct","est","logged"}}.
    # Oppdateres ved last, ikke sanntid. metric: timer(std) | auto | deloppgaver | stadium.
    @api.model
    def get_progress(self, model, ids, metric=None):
        ids = [i for i in (ids or []) if i]
        if not ids:
            return {}
        if not metric:
            metric = self.env["ir.config_parameter"].sudo().get_param(
                "fiq_gui_control.progress_metric", "timer")
        if model == "project.task":
            recs = self.env["project.task"].browse(ids).exists()
            return {t.id: self._task_progress(t, metric) for t in recs}
        if model == "project.project":
            return self._project_progress(ids, metric)
        return {}

    @staticmethod
    def _mk(pct, est=0.0, logged=0.0):
        """Normalisert fremdriftsobjekt: prosent + estimerte/førte timer."""
        return {
            "pct": max(0, min(100, int(round(pct or 0)))),
            "est": round(est or 0.0, 1),
            "logged": round(logged or 0.0, 1),
        }

    def _stage_is_done(self, stage):
        if not stage:
            return False
        if "fold" in stage._fields and stage.fold:
            return True
        if "is_closed" in stage._fields and getattr(stage, "is_closed", False):
            return True
        return False

    def _task_progress(self, task, metric):
        # 🎚 Manuell %-overstyring (detaljboksen): erstatter eller adderes til timebasert
        mode = getattr(task, "fiq_pct_mode", False) or "av"
        if mode != "av":
            h = self._task_hours(task) or self._mk(0)
            base = h["pct"] if mode == "adder" else 0
            return self._mk(base + (task.fiq_manual_pct or 0.0), h["est"], h["logged"])
        # STANDARD timer: førte ÷ estimerte timer
        if metric == "timer":
            h = self._task_hours(task)
            return h if h is not None else self._mk(0)
        if metric == "deloppgaver":
            return self._mk(self._task_subtasks(task) or 0)
        if metric == "stadium":
            return self._mk(self._task_stage(task))
        # auto: timer (m/ estimat) -> deloppgaver -> stadium
        h = self._task_hours(task)
        if h is not None and h["est"] > 0:
            return h
        v = self._task_subtasks(task)
        if v is not None:
            return self._mk(v)
        return self._mk(self._task_stage(task))

    def _task_hours(self, task):
        """Timebasert: effective_hours (ført) ÷ allocated_hours (estimert)."""
        f = task._fields
        if "allocated_hours" in f and "effective_hours" in f:
            try:
                est = task.allocated_hours or 0.0
                logged = task.effective_hours or 0.0
                pct = (logged * 100.0 / est) if est > 0 else 0
                return self._mk(pct, est, logged)
            except Exception:
                pass
        return None

    def _task_subtasks(self, task):
        """Andel ferdige deloppgaver (stadium fold/is_closed)."""
        if "child_ids" in task._fields:
            try:
                kids = task.child_ids
                if kids:
                    done = sum(
                        1 for k in kids
                        if self._stage_is_done(k.stage_id if "stage_id" in k._fields else False)
                    )
                    return int(round(done * 100.0 / len(kids)))
            except Exception:
                pass
        return None

    def _task_stage(self, task):
        """Posisjon i stadierekka (ferdig=100, ellers proporsjonalt)."""
        if "stage_id" not in task._fields or not task.stage_id:
            return 0
        if self._stage_is_done(task.stage_id):
            return 100
        try:
            ordered = self.env["project.task.type"].search([], order="sequence, id").ids
            sid = task.stage_id.id
            if sid in ordered and len(ordered) > 1:
                return int(round(ordered.index(sid) * 100.0 / (len(ordered) - 1)))
        except Exception:
            pass
        return 10  # i et stadium, men uten rekkefølge-signal

    def _project_progress(self, ids, metric):
        """Prosjekt-fremdrift STANDARD = timebasert rollup: Σførte ÷ Σestimerte
        over prosjektets oppgaver. Fallback: andel ferdige oppgaver."""
        Task = self.env["project.task"]
        f = Task._fields
        out = {pid: self._mk(0) for pid in ids}
        # Timebasert rollup (search_read regner effective_hours pr post → robust)
        if "allocated_hours" in f and "effective_hours" in f:
            try:
                agg = {}
                recs = Task.search_read(
                    [("project_id", "in", ids)],
                    ["project_id", "allocated_hours", "effective_hours"])
                for r in recs:
                    pid = r["project_id"][0] if r.get("project_id") else None
                    if pid is None:
                        continue
                    a = agg.setdefault(pid, [0.0, 0.0])
                    a[0] += r.get("allocated_hours") or 0.0
                    a[1] += r.get("effective_hours") or 0.0
                if agg:
                    for pid, (est, logged) in agg.items():
                        pct = (logged * 100.0 / est) if est > 0 else 0
                        out[pid] = self._mk(pct, est, logged)
                    return out
            except Exception:
                pass
        # Fallback: andel ferdige oppgaver (ferdig-stadium)
        try:
            Stage = self.env["project.task.type"]
            total = {}
            for grp in Task._read_group([("project_id", "in", ids)], ["project_id"], ["__count"]):
                if grp[0]:
                    total[grp[0].id] = grp[1]
            done_dom = [("project_id", "in", ids)]
            if "fold" in Stage._fields:
                done_dom.append(("stage_id.fold", "=", True))
            elif "is_closed" in Stage._fields:
                done_dom.append(("stage_id.is_closed", "=", True))
            done = {}
            for grp in Task._read_group(done_dom, ["project_id"], ["__count"]):
                if grp[0]:
                    done[grp[0].id] = grp[1]
            for pid in ids:
                n = total.get(pid, 0)
                out[pid] = self._mk(done.get(pid, 0) * 100.0 / n if n else 0)
        except Exception:
            pass
        return out

    @api.model
    def get_areas(self):
        """Sidemeny: fagområde-treet lest fra Odoo prosjekt-hierarkiet (SSOT — speiler
        SP-strukturen, ingen hardkodet liste). Områder = barn av toppnivå-prosjektene
        (firma-roten, f.eks. «0.040 VD (MP)»); underområder = barnas barn.
        «2 ADM (MP)» → nr «2», navn «ADM». Defensivt/felt-guardet."""
        P = self.env["project.project"]
        if "parent_id" not in P._fields:
            return []

        def parse(name):
            m = re.match(r"^\s*(\d+(?:\.\d+)*)\s+(.+?)\s*(?:\((?:MP|MT)\))?\s*$", name or "")
            return (m.group(1), m.group(2)) if m else (None, None)

        def sortkey(nr):
            return [int(p) for p in nr.split(".")]

        out = []
        try:
            roots = P.search([("parent_id", "=", False), ("active", "=", True)])
            for a in P.search([("parent_id", "in", roots.ids), ("active", "=", True)]):
                nr, name = parse(a.name)
                if not nr:
                    continue
                subs = []
                for s in P.search([("parent_id", "=", a.id), ("active", "=", True)]):
                    snr, sname = parse(s.name)
                    if snr:
                        subs.append({"id": s.id, "nr": snr, "name": sname})
                subs.sort(key=lambda x: sortkey(x["nr"]))
                out.append({"id": a.id, "nr": nr, "name": name, "subs": subs})
            out.sort(key=lambda x: sortkey(x["nr"]))
        except Exception:
            return []
        return out

    @api.model
    def get_children(self, model, parent_id):
        """Utvid-funksjon: underprosjekter (project.project via parent_id) eller
        deloppgaver (project.task via parent_id). Kjøres som brukeren (record rules).
        Defensivt/felt-guardet."""
        out = []
        try:
            if model == "project.project":
                P = self.env["project.project"]; f = P._fields
                dom = [("parent_id", "=", parent_id)]
                if "active" in f:
                    dom.append(("active", "=", True))
                for r in P.search(dom, order="id"):
                    out.append({
                        "id": r.id,
                        "no": (r.sequence_code if "sequence_code" in f else "") or "",
                        "name": r.name or "",
                        "taskCount": (r.task_count if "task_count" in f else 0) or 0,
                    })
            elif model == "project.task":
                T = self.env["project.task"]; f = T._fields
                for r in T.search([("parent_id", "=", parent_id)], order="id"):
                    out.append({
                        "id": r.id,
                        "no": (r.code if "code" in f else "") or "",
                        "name": r.name or "",
                    })
        except Exception:
            pass
        return out

    @api.model
    def get_detaljer(self, model, res_id):
        """Detaljer-panelet (inspektor): beskrivelse + logg (interne meldinger) +
        e-post + dokumenter (vedlegg) for valgt post. Kjøres som brukeren →
        record rules styrer tilgang. Alt defensivt/felt-guardet."""
        out = {"beskrivelse": "", "logg": [], "epost": [], "dok": []}
        try:
            rec = self.env[model].browse(res_id)
            if not rec.exists():
                return out
            if "description" in rec._fields:
                out["beskrivelse"] = rec.description or ""
            # Logg + e-post (mail.message på posten)
            msgs = self.env["mail.message"].search(
                [("model", "=", model), ("res_id", "=", res_id),
                 ("message_type", "in", ["email", "comment", "notification"])],
                order="date desc", limit=30)
            for m in msgs:
                author = m.author_id.display_name if m.author_id else (m.email_from or "—")
                item = {
                    "id": m.id,
                    "author": author,
                    "date": m.date.strftime("%d.%m %H:%M") if m.date else "",
                    "text": (m.preview or "").strip()[:200],
                }
                if m.message_type == "email":
                    item["subject"] = (m.subject or "").strip()
                    out["epost"].append(item)
                else:
                    out["logg"].append(item)
            # Dokumenter (vedlegg)
            atts = self.env["ir.attachment"].search(
                [("res_model", "=", model), ("res_id", "=", res_id)], order="id desc", limit=30)
            for a in atts:
                # mimetype + checksum → forhåndsvisning (FileViewer); ALDRI nedlasting
                out["dok"].append({
                    "id": a.id,
                    "name": a.name or _("Document"),
                    "mimetype": a.mimetype or "",
                    "checksum": a.checksum or "",
                })
        except Exception:
            pass
        return out

    @api.model
    def action_upgrade_module(self):
        """«Oppgrader» rett fra Kontrollrommet — samme som Oppgrader-knappen i Apper.
        Kontrollert løft: FIQ-admin-gruppen (eller Odoo Settings-admin) kan oppgradere
        AKKURAT denne modulen, uavhengig av tekniske innstillingsrettigheter."""
        if not (self.env.user.has_group("fiq_gui_control.group_admin")
                or self.env.user.has_group("base.group_system")):
            raise AccessError(_("Only administrators can upgrade the Control room."))
        mod = self.env["ir.module.module"].sudo().search([("name", "=", "fiq_gui_control")], limit=1)
        if mod and mod.state == "installed":
            mod.button_immediate_upgrade()
        return True

    @api.model
    def set_ai_cockpit_url(self, url):
        """Endre cockpit-adressen rett fra AI Kontrollrom-flaten — config-drevet
        (systemparameter fiq_gui_control.ai_cockpit_url), så adressen kan byttes
        UTEN ny modulversjon. Kontrollert løft: FIQ-admin eller Settings-admin."""
        if not (self.env.user.has_group("fiq_gui_control.group_admin")
                or self.env.user.has_group("base.group_system")):
            raise AccessError(_("Only administrators can change the cockpit address."))
        url = (url or "").strip()
        if url and not url.startswith(("https://", "http://")):
            url = "https://" + url
        self.env["ir.config_parameter"].sudo().set_param(
            "fiq_gui_control.ai_cockpit_url", url)
        return url

    # ---- «KREVER HANDLING NÅ» — globalt over hele AI-scopet (alle 0.-røttene) ----------
    @api.model
    def get_krever(self):
        """Brukerens åpne oppgaver på tvers av AI-prosjektene, m/ OPPGAVENR + PROSJEKT.
        Forsinkede først. Vises ALLTID øverst i AI KTRL."""
        out = []
        try:
            P = self.env["project.project"]
            roots = P.search([("parent_id", "=", False), ("name", "=ilike", "0.%"),
                              ("active", "=", True)])
            if not roots:
                return out
            T = self.env["project.task"]
            f = T._fields
            today = fields.Date.context_today(self)
            for t in T.search([("project_id", "child_of", roots.ids),
                               ("user_ids", "in", [self.env.uid])],
                              order="date_deadline asc", limit=60):
                if self._stage_is_done(t.stage_id if "stage_id" in f else False):
                    continue
                over = False
                try:
                    over = bool(t.date_deadline
                                and fields.Date.to_date(str(t.date_deadline)[:10]) < today)
                except Exception:
                    over = False
                out.append({
                    "id": t.id,
                    "no": (t.code if "code" in f else "") or "",
                    "name": t.name or "",
                    "prosjekt": t.project_id.name or "",
                    "over": over,
                })
            out.sort(key=lambda r: (not r["over"], r["no"]))
            out = out[:8]
        except Exception:
            pass
        return out

    # ---- AI Økter: øktene/agentene rapporterer hit (prosjekt «AI Økter (MP)») ----------
    @api.model
    def get_okter(self):
        """Økt-listen i AI KTRL: oppgavene i «AI Økter (MP)» m/ status + siste rapport.
        Kommunikasjon: Gjermund svarer i flaten → message_post på øktens oppgave."""
        out = []
        try:
            proj = self.env["project.project"].search(
                [("name", "ilike", "AI Økter")], limit=1)
            if not proj:
                return out
            Msg = self.env["mail.message"]
            for t in self.env["project.task"].search(
                    [("project_id", "=", proj.id)], order="id"):
                m = Msg.search(
                    [("model", "=", "project.task"), ("res_id", "=", t.id),
                     ("message_type", "in", ["comment", "notification"])],
                    order="date desc", limit=1)
                out.append({
                    "id": t.id,
                    "name": t.name or "",
                    "ferdig": self._stage_is_done(t.stage_id),
                    "sist": m.date.strftime("%d.%m %H:%M") if m and m.date else "",
                    "melding": html2plaintext(m.body or "").strip()[:160] if m and m.body else ((m.preview or "").strip()[:160] if m else ""),
                })
        except Exception:
            pass
        return out

    @api.model
    def post_okt_melding(self, task_id, text):
        """Send melding til en økt: legges i øktens chatter — øktene leser ved hver synk."""
        t = self.env["project.task"].browse(task_id).exists()
        if not t or not (text or "").strip():
            return False
        t.message_post(body=text.strip())
        return True

    # ---- AI-cockpit: scope-meny (Kunde / Prosjekt-Prosess / 0.00 IQ) -------------------
    @api.model
    def get_cockpit_scope(self):
        """Toppmenyen i cockpiten. «Kunder» = KUNDENE AV AI-LØSNINGEN (hjernene under IQ),
        dvs. toppnivå-røttene i prosjekt-treet (0.00 IQ, 0.040 VD, …) — IKKE res.partner.
        + full prosjektliste (uten maler)."""
        P = self.env["project.project"]
        f = P._fields
        dom = [("active", "=", True)]
        if "is_template" in f:
            dom.append(("is_template", "=", False))
        # AI-røttene = hjernene (nummerserien «0.» — 0.00 IQ, 0.040 VD, …).
        # AI KTRL handler KUN om AI-prosjektene, aldri hele prosjektregisteret.
        kunder, ai_root_ids = [], []
        if "parent_id" in f:
            for r in P.search(dom + [("parent_id", "=", False), ("name", "=ilike", "0.%")],
                              order="name"):
                kunder.append({"id": r.id, "name": r.name or ""})
                ai_root_ids.append(r.id)
        pdom = dom + [("id", "child_of", ai_root_ids)] if ai_root_ids else dom + [("id", "=", 0)]
        projs = P.search(pdom, order="name")
        # AI-plattform vs interne: taggen «AI-plattform» (Coworker setter den på alt den oppretter)
        tag = self.env["project.tags"].search([("name", "=", "AI-plattform")], limit=1)
        return {
            "kunder": kunder,
            "prosjekter": [{
                "id": p.id,
                "no": (p.sequence_code if "sequence_code" in f else "") or "",
                "name": p.name or "",
                "ai": bool(tag and "tag_ids" in f and tag.id in p.tag_ids.ids),
            } for p in projs],
        }

    @api.model
    def get_cockpit_diagram(self, root_id=False, iq=False, slag="ai"):
        """Fremdrifts-/forbruksdiagram over ALLE prosjekter i valgt scope:
        per prosjekt {no, name, pct, est, logged}. root_id = valgt kunde/hjerne
        (toppnivå-rot; child_of). iq=True = 0.00 IQ-serien (navneprefiks «0.»)."""
        P = self.env["project.project"]
        f = P._fields
        dom = [("active", "=", True)]
        if "is_template" in f:
            dom.append(("is_template", "=", False))
        if root_id:
            dom += [("id", "child_of", int(root_id)), ("id", "!=", int(root_id))]
        elif iq:
            dom.append(("name", "=ilike", "0.%"))
        else:
            # «Alle» = alle AI-prosjektene (under hjernene/0.-røttene) — ALDRI hele registeret
            roots = P.search([("parent_id", "=", False), ("name", "=ilike", "0.%"),
                              ("active", "=", True)]) if "parent_id" in f else P.browse()
            dom += [("id", "child_of", roots.ids)] if roots else [("id", "=", 0)]
        # AI-plattform vs interne (knappen i toppmenyen): taggen «AI-plattform»
        tag = self.env["project.tags"].search([("name", "=", "AI-plattform")], limit=1)
        if tag and "tag_ids" in f:
            if slag == "ai":
                dom.append(("tag_ids", "in", tag.id))
            elif slag == "interne":
                dom.append(("tag_ids", "not in", tag.id))
        projs = P.search(dom, order="name", limit=120)
        prog = self._project_progress(projs.ids, "timer") if projs else {}

        def _root(p):
            cur, hop = p, 0
            while "parent_id" in f and cur.parent_id and hop < 20:
                cur = cur.parent_id
                hop += 1
            return cur

        out = []
        for p in projs:
            pr = prog.get(p.id) or self._mk(0)
            rt = _root(p)
            out.append({
                "id": p.id,
                "no": (p.sequence_code if "sequence_code" in f else "") or "",
                "name": p.name or "",
                "pct": pr["pct"], "est": pr["est"], "logged": pr["logged"],
                "taskCount": (p.task_count if "task_count" in f else 0) or 0,
                # Gruppering på kunde/hjerne (toppnivå-rot) ved «Alle»
                "root_id": rt.id, "root_name": rt.name or "", "is_root": rt.id == p.id,
            })
        return out

    # ---- AI-cockpit (fremdrifts-hub) — speiler Artifact-cockpiten mot ekte oppgaver -----
    @api.model
    def get_cockpit(self, project_id=False):
        """Cockpit-flaten i AI Kontrollrom: grupper (rotprosjekt + underprosjekter) med
        oppgaver, Du/AI-merke, status og «krever handling». Config-drevet: systemparameter
        `fiq_gui_control.cockpit_project_id` = rotprosjektets id. Defensivt/felt-guardet."""
        ICP = self.env["ir.config_parameter"].sudo()
        out = {"groups": [], "tot": {"done": 0, "pag": 0, "vent": 0, "tot": 0, "pct": 0},
               "krever": [], "root": ""}
        try:
            pid = int(project_id or 0) \
                or int(ICP.get_param("fiq_gui_control.cockpit_project_id", "0") or 0)
        except Exception:
            pid = 0
        if not pid:
            return out
        P = self.env["project.project"]
        root = P.browse(pid).exists()
        if not root:
            return out
        out["root"] = root.name or ""
        projects = list(root)
        if "parent_id" in P._fields:
            projects += list(P.search(
                [("parent_id", "=", root.id), ("active", "=", True)], order="id"))
        Task = self.env["project.task"]
        f = Task._fields
        today = fields.Date.context_today(self)
        stmap = {"ferdig": "done", "pagar": "pag", "venter": "vent"}
        for p in projects:
            tasks = Task.search([("project_id", "=", p.id)], order="id")
            if not tasks:
                continue
            rows, done = [], 0
            for t in tasks:
                stage = t.stage_id if "stage_id" in f and t.stage_id else False
                st = "ferdig" if self._stage_is_done(stage) else "venter"
                nm = (stage.name or "").lower() if stage else ""
                if st != "ferdig" and ("pågår" in nm or "progress" in nm or "doing" in nm):
                    st = "pagar"
                if st == "ferdig":
                    done += 1
                over = False
                try:
                    over = bool(t.date_deadline
                                and fields.Date.to_date(str(t.date_deadline)[:10]) < today)
                except Exception:
                    over = False
                rows.append({
                    "id": t.id,
                    "no": (t.code if "code" in f else "") or "",
                    "name": t.name or "",
                    "who": "du" if t.user_ids else "ai",
                    "st": st,
                    "stage": stage.name if stage else "",
                    "over": over,
                    "frist": str(t.date_deadline)[:10] if t.date_deadline else "",
                })
                out["tot"]["tot"] += 1
                out["tot"][stmap[st]] += 1
            out["groups"].append({
                "id": p.id,
                "no": (p.sequence_code if "sequence_code" in P._fields else "") or "",
                "name": p.name or "",
                "done": done, "total": len(rows), "tasks": rows,
            })
        mine = [r for g in out["groups"] for r in g["tasks"]
                if r["who"] == "du" and r["st"] != "ferdig"]
        mine.sort(key=lambda r: (not r["over"], r["no"]))
        out["krever"] = mine[:4]
        t = out["tot"]
        t["pct"] = int(round(t["done"] * 100.0 / t["tot"])) if t["tot"] else 0
        return out

    @api.model
    def cockpit_toggle(self, task_id):
        """Kryss av i cockpiten: flytt oppgaven til prosjektets ferdig-stadium
        (fold/is_closed); allerede ferdig → tilbake til første åpne stadium.
        Kjøres som brukeren → tilgangsregler styrer."""
        t = self.env["project.task"].browse(task_id).exists()
        if not t:
            return False
        Stage = self.env["project.task.type"]
        dom = [("project_ids", "in", t.project_id.id)] \
            if "project_ids" in Stage._fields and t.project_id else []
        stages = Stage.search(dom, order="sequence, id")
        if not stages:
            return False
        done_st = stages.filtered(lambda s: self._stage_is_done(s))
        open_st = stages.filtered(lambda s: not self._stage_is_done(s))
        if self._stage_is_done(t.stage_id):
            if open_st:
                t.write({"stage_id": open_st[0].id})
        elif done_st:
            t.write({"stage_id": done_st[0].id})
        return True

    @api.model
    def get_deltagere(self, model, res_id):
        """Detaljer: prosjektdeltagere — prosjektleder + oppgave-ansvarlige. Kobles til
        fiq.project.role (rolle-innehavere) når rollemodellen er bygd. Defensivt."""
        out = []
        try:
            if model == "project.task":
                t = self.env["project.task"].browse(res_id).exists()
                if t and t.project_id:
                    model, res_id = "project.project", t.project_id.id
            if model != "project.project":
                return out
            p = self.env["project.project"].browse(res_id).exists()
            if not p:
                return out
            seen = set()
            if "user_id" in p._fields and p.user_id:
                out.append({"name": p.user_id.name, "rolle": _("Project manager")})
                seen.add(p.user_id.id)
            for t in self.env["project.task"].search([("project_id", "=", p.id)], limit=200):
                for u in t.user_ids:
                    if u.id not in seen:
                        seen.add(u.id)
                        out.append({"name": u.name, "rolle": _("Participant")})
        except Exception:
            pass
        return out

    @api.model
    def get_kalender(self, start, end, month_start, month_end, user_id=None):
        """Møter + aktiviteter i VALGT periode (Dag/Uke/Måned/Alle) for VALGT person
        (standard = innlogget; kollega leses sudo som intern busy-/oppfølgingsvisning).
        mnd = datoer i vist måned som har møter → mini-månedskalenderen."""
        uid = user_id or self.env.uid
        other = bool(user_id) and user_id != self.env.uid
        user = self.env["res.users"].sudo().browse(uid).exists()
        out = {"moter": [], "aktiviteter": [], "mnd": []}
        if not user:
            return out
        Ev = self.env["calendar.event"].sudo() if other else self.env["calendar.event"]
        Act = self.env["mail.activity"].sudo() if other else self.env["mail.activity"]
        try:
            evs = Ev.search([
                ("partner_ids", "in", user.partner_id.ids),
                ("start", "<", end), ("stop", ">=", start)], order="start", limit=60)
            for e in evs:
                st = fields.Datetime.context_timestamp(e, e.start) if e.start else None
                sl = fields.Datetime.context_timestamp(e, e.stop) if e.stop else None
                out["moter"].append({
                    "id": e.id, "name": e.name or "",
                    "dato": st.strftime("%d.%m") if st else "",
                    "tid": st.strftime("%H:%M") if st else "",
                    "slutt": sl.strftime("%H:%M") if sl else "",
                })
            # Måneds-markører: dager med MØTER (ikke aktiviteter)
            dager = set()
            for e in Ev.search([
                    ("partner_ids", "in", user.partner_id.ids),
                    ("start", "<", month_end), ("stop", ">=", month_start)], limit=300):
                st = fields.Datetime.context_timestamp(e, e.start) if e.start else None
                if st:
                    dager.add(st.strftime("%Y-%m-%d"))
            out["mnd"] = sorted(dager)
        except Exception:
            pass
        try:
            today = fields.Date.context_today(self)
            end_d = str(end)[:10]
            mdl_names = {}
            for a in Act.search([("user_id", "=", uid), ("date_deadline", "<=", end_d)],
                                order="date_deadline", limit=30):
                # Tilhørighet: modellens VISNINGSNAVN (Salg, Kontakt, Prosjekt …), ikke teknisk navn
                mn = a.res_model or ""
                if mn and mn not in mdl_names:
                    try:
                        mdl_names[mn] = self.env["ir.model"]._get(mn).name or mn
                    except Exception:
                        mdl_names[mn] = mn
                note = ""
                try:
                    from odoo.tools import html2plaintext
                    note = (html2plaintext(a.note or "") or "").strip()[:400]
                except Exception:
                    note = ""
                out["aktiviteter"].append({
                    "id": a.id,
                    "name": a.summary or (a.activity_type_id.name or _("Activity")),
                    "type": a.activity_type_id.name or "",
                    "frist": str(a.date_deadline or ""),
                    "forsinket": bool(a.date_deadline and a.date_deadline < today),
                    "model": a.res_model or "",
                    "modell_navn": mdl_names.get(mn, ""),
                    "res_id": a.res_id or 0,
                    "res_name": a.res_name or "",
                    "ansvarlig": a.user_id.name or "",
                    "note": note,
                })
        except Exception:
            pass
        return out

    @api.model
    def utsett_aktivitet(self, activity_id, dager=None, ny_dato=None):
        """Utsett en aktivitet: +N dager fra fristen (el. i dag), ELLER eksplisitt ny dato.
        Kjøres som brukeren → tilgangsregler styrer."""
        act = self.env["mail.activity"].browse(activity_id).exists()
        if not act:
            return False
        if ny_dato:
            act.write({"date_deadline": ny_dato})
        elif dager:
            base = act.date_deadline or fields.Date.context_today(self)
            act.write({"date_deadline": fields.Date.add(base, days=int(dager))})
        return str(act.date_deadline)

    @api.model
    def get_presence(self):
        """«Til stede nå»: interne brukere med SAMMENSATT status som farger HELE kortet:
           🟢 grønn = Til stede · 🟠 oransje = I møte / Ute · 🔴 rød = Fraværende / Ikke møtt.
           Kombinerer im_status (pålogget/borte/av) + pågående møte (calendar.event) +
           oppmøte (hr.attendance åpen = møtt på jobb). Alt defensivt/felt-guardet.
           Møte/oppmøte leses sudo (fri/opptatt-indikator på en delt tilstede-tavle)."""
        Users = self.env["res.users"]
        users = Users.search(
            [("share", "=", False), ("active", "=", True)],
            order="name", limit=24,
        )

        # Batch: hvem er i et møte NÅ (calendar.event der nå ∈ [start, stop]) → partner_ids
        in_meeting = set()
        try:
            now = fields.Datetime.now()
            evs = self.env["calendar.event"].sudo().search(
                [("start", "<=", now), ("stop", ">=", now)])
            for e in evs:
                in_meeting.update(e.partner_ids.ids)
        except Exception:
            pass

        # Batch: hvem har møtt på jobb (åpen hr.attendance, ingen check_out) → user_ids
        attendance_avail = False
        checked_in_users = set()
        try:
            open_att = self.env["hr.attendance"].sudo().search([("check_out", "=", False)])
            attendance_avail = True
            emp_ids = open_att.mapped("employee_id").ids
            if emp_ids:
                emps = self.env["hr.employee"].sudo().browse(emp_ids)
                checked_in_users = set(emps.mapped("user_id").ids)
        except Exception:
            attendance_avail = False

        # Bus-ferskhet: utlogging/lukket fane slutter å oppdatere last_poll → offline
        # etter ~3 min (im_status alene henger igjen lenge etter utlogging).
        bus_map = {}
        try:
            now = fields.Datetime.now()
            for bp in self.env["bus.presence"].sudo().search([("user_id", "in", users.ids)]):
                fresh = bool(bp.last_poll and (now - bp.last_poll).total_seconds() < 180)
                bus_map[bp.user_id.id] = (bp.status or "offline") if fresh else "offline"
        except Exception:
            bus_map = {}

        out = []
        for u in users:
            if u.id in bus_map:
                raw = bus_map[u.id]
            else:
                # Fallback: im_status (computed, krever bus). Les defensivt.
                try:
                    raw = u.im_status or "offline"
                except Exception:
                    raw = "offline"
            if raw.startswith("online"):
                im = "online"
            elif raw.startswith("away"):
                im = "away"
            else:
                im = "offline"

            meeting = u.partner_id.id in in_meeting
            moett = (u.id in checked_in_users) if attendance_avail else None

            # Fargelogikk for HELE kortet. OPPMØTE (innstemplet) er sterkeste signal =
            # «Til stede», UANSETT im_status (im_status er upålitelig uten sanntids-buss,
            # f.eks. på Staging). Deretter im_status som fallback.
            if meeting:
                farge, tekst = "orange", _("In a meeting")
            elif moett:
                farge, tekst = "green", _("Present")
            elif im == "online":
                farge, tekst = "green", _("Present")
            elif im == "away":
                farge, tekst = "orange", _("Out")
            elif attendance_avail:
                farge, tekst = "red", _("Not checked in")
            else:
                farge, tekst = "red", _("Absent")

            name = u.name or u.login or "—"
            parts = [p for p in name.replace("-", " ").split(" ") if p]
            if len(parts) >= 2:
                initialer = (parts[0][:1] + parts[-1][:1]).upper()
            elif parts:
                initialer = parts[0][:2].upper()
            else:
                initialer = "?"
            has_photo = False
            try:
                emp = self.env["hr.employee"].sudo().search(
                    [("user_id", "=", u.id)], limit=1)
                has_photo = bool(emp and emp.image_128)
            except Exception:
                has_photo = False

            out.append({
                "id": u.id,
                "partner_id": u.partner_id.id,
                "navn": name,
                "initialer": initialer,
                "status": im,        # bakoverkomp (dot)
                "farge": farge,      # green | orange | red – farger HELE kortet
                "tekst": tekst,      # Til stede | I møte | Ute | Fraværende | Ikke møtt
                "has_photo": has_photo,
            })
        return out

    @api.model
    def get_actions(self):
        """Resolverer kandidat-Odoo-handlinger som FAKTISK finnes i denne DB-en
        (env.ref-guard). Front-end sjekker om et handlingsnavn er 'tilgjengelig' før
        det gjør doAction; ellers vises «under utvikling»-varsel.
        depends = web+project → prosjekt-handlinger er alltid trygge; crm/sale/account
        må guardes (kan mangle i kundens DB)."""
        candidates = {
            "nytt_prosjekt": "project.open_view_project_all",
            "salgsordre": "sale.action_orders",
            "nytt_leads": "crm.crm_lead_all_leads",
            "tilbud": "sale.action_quotations",
            "kunde": "base.action_partner_form",
            "dokument": "documents.document_action",
            # Kalender + aktiviteter (MVP: native views; den todelte «Dagens møter»-flaten kommer)
            "kalender": "calendar.action_calendar_event",
            "aktivitet": "mail.mail_activity_action",
            # De andre kontrollpanelene (fiq_gui_*-flatene) — vises i Styring-menyen når installert
            "gui_prj": "fiq_gui_prj.action_fiq_gui_prj",
            "gui_crm": "fiq_gui_crm.action_fiq_gui_crm",
            "gui_leads": "fiq_gui_crm_leads.action_fiq_gui_crm_leads",
            "gui_so": "fiq_gui_crm_so.action_fiq_gui_crm_so",
            "gui_epost": "fiq_gui_epost.action_fiq_gui_epost",
            "gui_rgs": "fiq_gui_rgs.action_fiq_gui_rgs",
            # Kunnskap: artikler/maler (Odoo Knowledge — hjemmesiden)
            "kunnskap": "knowledge.ir_actions_server_knowledge_home_page",
            # Enkel-flatens store arbeider-knapper (native der det finnes)
            "timer": "hr_timesheet.act_hr_timesheet_line",
            "godkjenning": "approvals.approval_request_action_to_review",
        }
        out = {}
        for key, xmlid in candidates.items():
            out[key] = xmlid if self.env.ref(xmlid, raise_if_not_found=False) else False
        return out

    @api.model
    def get_kommunikasjon(self, period="uke", limit=40):
        """Communication view (GENERIC – all models/records, not SDV-specific):
        the latest communication (email/messages) ON records the user can access, with a link.
        period = dag|uke|maaned|alle. Runs as the user → record rules control visibility."""
        Msg = self.env["mail.message"]
        domain = [
            ("message_type", "in", ["email", "comment"]),
            ("model", "!=", False),
            ("res_id", "!=", False),
            ("model", "not in", ["discuss.channel", "mail.channel"]),
        ]
        days = {"dag": 1, "uke": 7, "maaned": 30}.get(period)
        if days:
            domain.append(("date", ">=", fields.Datetime.now() - timedelta(days=days)))
        msgs = Msg.search(domain, limit=limit, order="date desc")
        out = []
        for m in msgs:
            element = ""
            try:
                element = self.env[m.model].browse(m.res_id).display_name or ""
            except Exception:
                element = ""
            author = m.author_id.display_name if m.author_id else (m.email_from or "—")
            subject = (m.subject or m.preview or "").strip()
            # Direction "sent from": messages written by an internal user = SENT (outgoing/
            # logged by us); everything else (external sender, plain incoming email) = RECEIVED.
            # Makes it easy for AI/user to tell what came in vs. what we sent.
            internal = bool(
                m.author_id
                and m.author_id.user_ids
                and any(not u.share for u in m.author_id.user_ids)
            )
            is_email = m.message_type == "email"
            out.append({
                "id": m.id,
                "kind": _("Email") if is_email else _("Message"),
                "ktype": "mail" if is_email else "msg",
                "author": author,
                "author_id": m.author_id.id if m.author_id else False,
                "direction": "sendt" if internal else "mottatt",
                "subject": subject[:90] or _("(no subject)"),
                "date": m.date.strftime("%d.%m %H:%M") if m.date else "",
                "model": m.model,
                "res_id": m.res_id,
                "element": element,
            })
        return out

    @api.model
    def action_reply(self, message_id, reply_all=False):
        """Reply / Reply all on a communication → open the mail composer pre-filled.
        CC/BCC available via mail_composer_cc_bcc. (FIQ compose canonicalized later.)"""
        msg = self.env["mail.message"].browse(message_id)
        partners = msg.author_id
        if reply_all:
            partners |= msg.partner_ids
        ctx = {
            "default_model": msg.model,
            "default_res_ids": [msg.res_id],
            "default_parent_id": msg.id,
            "default_subject": "Re: %s" % (msg.subject or ""),
            "default_composition_mode": "comment",
            "default_partner_ids": [(6, 0, partners.ids)],
        }
        return {
            "type": "ir.actions.act_window",
            "name": _("Reply all") if reply_all else _("Reply"),
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": ctx,
        }

    # Candidate dashboards (Odoo's native analyses/dashboards). Shown ONLY if the xmlid exists
    # in the customer DB → safe across tenants (env.ref guard, no hard dependencies).
    _DASHBOARD_CANDIDATES = [
        ("spreadsheet_dashboard.ir_actions_dashboard_action", "Dashboards (Odoo)"),
        ("sale.action_order_report_all", "Sales analysis"),
        ("account.action_account_invoice_report_all", "Invoice analysis"),
        ("purchase.action_purchase_order_report_all", "Purchase analysis"),
        ("crm.crm_opportunity_report_action", "Pipeline analysis"),
        ("hr_timesheet.timesheet_action_report_by_project", "Timesheet analysis"),
    ]

    @api.model
    def get_dashboards(self):
        """Returns the native dashboard/analysis actions that actually exist in this DB
        (xmlid resolves). The front-end opens them in-page via doAction(xmlid) – SSOT,
        no duplication of Odoo's own dashboards."""
        out = []
        for xmlid, label in self._DASHBOARD_CANDIDATES:
            if self.env.ref(xmlid, raise_if_not_found=False):
                out.append({"xmlid": xmlid, "label": _(label)})
        return out

    @api.model
    def _action_set_home_all(self):
        """Admin-controlled: set the Control room as start page ONLY for companies where
        `fiq_control_as_home` is ON; otherwise unlock (clear our home action).
        Called via <function> on install AND upgrade. Never forced on everyone."""
        action = self.env.ref("fiq_gui_control.action_fiq_gui_control", raise_if_not_found=False)
        if not action:
            return True
        Users = self.env["res.users"]
        for comp in self.env["res.company"].search([]):
            users = Users.search([("share", "=", False), ("company_id", "=", comp.id)])
            if comp.fiq_control_as_home:
                users.write({"action_id": action.id})
            else:
                # Unlock: clear only those that actually point to the Control room
                locked = users.filtered(lambda u: u.action_id and u.action_id.id == action.id)
                if locked:
                    locked.write({"action_id": False})
        return True
