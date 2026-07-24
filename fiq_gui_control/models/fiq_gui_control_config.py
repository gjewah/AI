import json
import logging
import re
from datetime import datetime, timedelta
from typing import ClassVar

import pytz
from odoo import _, api, fields, models
from odoo.exceptions import AccessError
from odoo.modules.module import get_manifest
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"]


class FiqControlRoomConfig(models.Model):
    """Per-user/per-company setup for the Control room (FIQ's own governance layer
    on top of res.groups): level + which widgets are shown. Governed by access groups
    + record rules (a user only sees their own)."""

    _name = "fiq.gui.control.config"
    _description = "FIQ Control room – user setup"
    _rec_name = "user_id"

    # Ingen `string=` på disse to: Odoo utleder «User» fra `user_id` og «Company» fra
    # `company_id` automatisk. En eksplisitt etikett som gjentar utledningen er støy som
    # må vedlikeholdes i to lag — og den blokkerte CI-porten (W8113).
    user_id = fields.Many2one(
        "res.users",
        required=True,
        index=True,
        ondelete="cascade",
        default=lambda s: s.env.user,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        index=True,
        default=lambda s: s.env.company,
    )
    level = fields.Selection(
        [("pulse", "Pulse (summary)"), ("balansert", "Balanced"), ("detaljert", "Detailed")],
        string="Detail level",
        default="balansert",
        required=True,
        help="Role-based detail level: Pulse (executive) · Balanced (project manager) · Detailed (power).",
    )
    # ── POSISJONSDELING — ÉN BRYTER FOR BEGGE FLATER (Gjermund 20.07) ──────────────────
    #
    # Gjermunds krav, ordrett: «det skal være en egen toggle som slår av GPS for Odoo OG
    # Claude for brukeren automatisk, men varsler om det og lar brukeren slå den på om
    # hen bevisst ønsker det.»
    #
    # 🔑 HVORFOR ÉN BRYTER OG IKKE TO — begrunnelsen er viktigere enn feltet:
    # gjaldt avslaget bare Odoo, ville brukeren tro hen var usynlig mens mobilen fortsatt
    # delte posisjon. **Det er den farligste varianten, fordi den ser trygg ut.** Én bryter
    # er det eneste som gjør at brukeren VET hvor hen står.
    #
    # 🛑 Feltet sier bare OM posisjon skal deles. Det lagrer ingen posisjon — verken her
    # eller andre steder i denne modulen. Selve innsamlingen er ikke bygget, og krever
    # eget rettslig grunnlag ([[fiq-oppmote-lokasjon-gdpr]]). Dette er bryteren, ikke sporet.
    del_posisjon = fields.Boolean(
        "Share my location",
        default=False,
        help="Off by default. Covers BOTH the control room and the mobile assistant — "
        "one switch, so you always know where you stand.",
    )
    # Satt av systemet når ferie slår den av, slik at vi kan VARSLE brukeren om at det
    # skjedde. Uten dette ville avslaget vært stille — og et stille avslag er like
    # forvirrende som en stille deling.
    del_posisjon_auto_av = fields.Boolean(
        "Turned off automatically",
        default=False,
        help="Set when leave switched sharing off, so the user can be told it happened.",
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
    # Flater brukeren selv har skrudd AV (komma-liste med flate-nøkler). Lagres på serveren,
    # ikke i localStorage, så «mitt KR» følger brukeren mellom maskiner. Kan bare SKJULE —
    # tilgang avgjøres av gruppene i get_fiq_flater(), aldri av dette feltet.
    skjulte_flater = fields.Char("Hidden flates", default="")
    # Foldede grupper/rader, per bruker+firma. JSON: {"<omraade>": ["<id>", ...]}.
    # «Område» = hvilken liste/tre det gjelder (prosjekttre, avviksliste …), så to flater
    # aldri folder hverandres rader. Nøkler er ID-er, ALDRI navn — se _fold_nokkel().
    fold_state = fields.Text("Collapsed groups", default="{}")

    # Odoo 19: use models.Constraint (not the deprecated _sql_constraints)
    _user_company_uniq = models.Constraint(
        "unique(user_id, company_id)",
        "One Control room setup per user per company.",
    )

    # =====================================================================
    #  Firma-scope — DELT KJERNE for alle FIQ-flater (Meldingssenter, AI KR, PRJ …)
    #
    #  Tenant-kanonen: hvem som ser på tvers av firmaer avgjøres av en HARD
    #  Odoo-mekanisme (sikkerhetsgruppe), aldri av en prompt, en klient-parameter
    #  eller en visnings-innstilling. Flatene kaller hjelperne under; ingen flate
    #  bygger sin egen scope-logikk.
    # =====================================================================

    @api.model
    def har_000_rettighet(self):
        """Har den innloggede plattform-nivå (000) = innsyn på tvers av firmaer?

        Fail-closed: alt annet enn et utvetydig JA betyr nei. En feil under
        oppslaget gir ETT firma, aldri alle.
        """
        try:
            return self.env.user.has_group("fiq_gui_control.group_000_kryss_firma")
        except Exception:
            return False

    @api.model
    def tillatte_firmaer(self):
        """Firmaene den innloggede lovlig kan se — kilden for all scope.

        Uten 000: kun det aktive firmaet. Med 000: firmaene brukeren er medlem av.
        Merk: 000 utvider til brukerens EGNE firmaer, ikke til alle firmaer i basen —
        kryss-tenant utover det er en egen sak (avtale + DPA), ikke en gruppe.
        """
        if self.har_000_rettighet():
            return self.env.user.company_ids.ids or self.env.company.ids
        return self.env.company.ids

    @api.model
    def firma_domene(self, firm=False, felt="company_id", inkluder_uten_firma=True):
        """Bygg et Odoo-domene som avgrenser til det brukeren lovlig kan se.

        `firm` er klientens valg (f.eks. firmavelgeren i toppmenyen). Den kan bare
        SNEVRE INN innenfor det sesjonen allerede tillater — aldri utvide. Et ugyldig
        eller uautorisert valg faller tilbake til hele det lovlige scopet, ikke til feil.

        :param felt: firmafeltet på modellen (noen modeller bruker record_company_id).
        :param inkluder_uten_firma: ta med poster uten firma-tilhørighet. Kun relevant
            med 000: plattform-nivået eier de firma-løse postene.
        """
        tillatte = self.tillatte_firmaer()
        if firm:
            try:
                valgt = int(firm)
            except (TypeError, ValueError):
                valgt = 0
            if valgt in tillatte:
                return [(felt, "=", valgt)]
            return [(felt, "in", tillatte)]
        if inkluder_uten_firma and self.har_000_rettighet():
            return ["|", (felt, "in", tillatte), (felt, "=", False)]
        return [(felt, "in", tillatte)]

    def _get_or_create_current(self):
        rec = self.search([("user_id", "=", self.env.uid), ("company_id", "=", self.env.company.id)], limit=1)
        if not rec:
            rec = self.create({})
        return rec

    @api.model
    def get_my_config(self):
        rec = self._get_or_create_current()
        # Ferie slår av posisjonsdeling HER, ved oppslag — ikke i en nattlig jobb.
        # En jobb som går én gang i døgnet ville latt posisjonen stå på i timevis etter
        # at ferien startet, og en bryter som slår av «snart» kan man ikke stole på.
        # Returverdien brukes til å VARSLE: et stille avslag er like forvirrende som
        # en stille deling.
        posisjon_nettopp_av = rec._ferie_slar_av_posisjon()
        comp = self.env.company
        # Logo-kilde: fiq_partner_relasjon gjør firmaets EGEN logo til standard, og lar
        # fiq_control_logo overstyre der den vanlige logoen ikke leses på mørk bakgrunn.
        # Uten den modulen: gammel oppførsel (kun overstyrings-feltet).
        logo = comp.fiq_brand_logo if "fiq_brand_logo" in comp._fields else comp.fiq_control_logo
        if logo:
            logo = logo.decode() if isinstance(logo, bytes) else logo
        # Firmavelgeren viser det sesjonen tillater — samme kilde som scope-hjelperen,
        # så velgeren aldri tilbyr noe server-siden vil avvise.
        companies = [
            {"id": c.id, "name": c.name} for c in self.env["res.company"].browse(self.tillatte_firmaer()).exists()
        ]
        # Config-drevet per-linje fremdrift (lag 2): form (bar/ring) + metrikk. Fornuftige
        # defaults, overstyrbare via system-parametere (Innstillinger → Teknisk → Parametere).
        ICP = self.env["ir.config_parameter"].sudo()
        return {
            "id": rec.id,
            "level": rec.level,
            # Posisjonsdeling: én bryter for BÅDE Kontrollrommet og mobilen.
            # `posisjon_varsel` er True kun i det oppslaget der ferien slo den av —
            # da skal brukeren få beskjed én gang, ikke hver gang siden lastes.
            "del_posisjon": rec.del_posisjon,
            "posisjon_varsel": posisjon_nettopp_av,
            "show": {w: bool(rec["show_" + w]) for w in WIDGETS},
            "is_admin": self.env.user.has_group("fiq_gui_control.group_admin"),
            # Plattform-nivå (000): styrer om «Alle firmaer» i det hele tatt tilbys.
            # Selve avgrensningen skjer server-side i firma_domene() — dette flagget
            # er kun for visningen, og gir ingen tilgang i seg selv.
            "har_000": self.har_000_rettighet(),
            # Company/branding resolved server-side (no dependency on the company service in OWL)
            "company_name": comp.name or "",
            "company_id": comp.id,
            "companies": companies,
            "accent": comp.fiq_control_accent or "#38B44A",
            "logo": (f"data:image/png;base64,{logo}") if logo else False,
            "progress_shape": ICP.get_param("fiq_gui_control.progress_shape", "bar"),
            "progress_metric": ICP.get_param("fiq_gui_control.progress_metric", "timer"),
            # Versjon: installert (DB, endres av «Oppgrader» i Apper) + filene på disk.
            # Avvik → GUI-et varsler «trykk Oppgrader» (fanger filer-nyere-enn-DB-fella).
            "version_installed": self._module_versions()[0],
            "version_files": self._module_versions()[1],
            # Auto-oppdatering: intervall i minutter (config-drevet, overstyrbar)
            "auto_refresh_min": int(ICP.get_param("fiq_gui_control.auto_refresh_min", "5") or 5),
            # Hvem kan kjøre modul-oppgradering fra brikken (FIQ-admin ELLER Settings-admin)
            "can_upgrade": (
                self.env.user.has_group("fiq_gui_control.group_admin") or self.env.user.has_group("base.group_system")
            ),
            # SP-lenker per fagområde (config-drevet, PER FIRMA): systemparameter
            # fiq_gui_control.sp_urls.<company_id> (fallback .sp_urls) = JSON {"1": "https://…", "8.50": "https://…"}
            "sp_urls": self._sp_urls(comp),
            # AI-cockpit (Artifact, interim til full Odoo-bygging): config-drevet URL
            "ai_cockpit_url": ICP.get_param("fiq_gui_control.ai_cockpit_url", ""),
            # 📌 Blokk-rekkefølge på flaten (per bruker)
            "widget_order": rec.widget_order or "",
            # 📋 Pågående oppgaver (config-drevet, vist i AI-fanen)
            "pagaende_oppgaver": self._pagaende_oppgaver(),
        }

    @api.model
    def _pagaende_oppgaver(self):
        """Pågående oppgaver vist i AI-fanen (config-drevet). Systemparameter
        fiq_gui_control.pagaende_oppgaver (JSON) overstyrer standarden — så listen
        kan vedlikeholdes uten ny modulversjon. Navn er innhold (norsk), ikke UI."""
        import json

        raw = self.env["ir.config_parameter"].sudo().get_param("fiq_gui_control.pagaende_oppgaver")
        if raw:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return [
            {
                "nr": "01",
                "navn": "Plattform-konsolidering — én FIQ-eid kilde",
                "hvem": "ai",
                "status": "pagar",
                "under": [
                    {"nr": "01.01", "navn": "Sikring — mist ingenting", "hvem": "ai", "status": "ferdig"},
                    {"nr": "01.02", "navn": "Kopier loym-modulene inn i plattformen", "hvem": "ai", "status": "apen"},
                    {"nr": "01.03", "navn": "Rydd bort de doble kopiene", "hvem": "ai", "status": "apen"},
                    {"nr": "01.04", "navn": "Koble FIQ (pilot) på + verifiser på test", "hvem": "ai", "status": "apen"},
                    {"nr": "01.05", "navn": "Rull ut til Vidir, SDV, JPC", "hvem": "ai", "status": "venter"},
                    {"nr": "01.06", "navn": "Versjonskontroll + rulle-bakover", "hvem": "ai", "status": "apen"},
                    {"nr": "01.07", "navn": "Oversiktsmodul i Kontrollrommet", "hvem": "ai", "status": "pagar"},
                ],
            },
            {
                "nr": "02",
                "navn": "Norsk + firmalogo i Kontrollrommet",
                "hvem": "ai",
                "status": "parkert",
                "under": [
                    {"nr": "02.01", "navn": "Norsk-språk-vask på flatene", "hvem": "ai", "status": "apen"},
                    {"nr": "02.02", "navn": "Firmalogo i topplinja", "hvem": "ai", "status": "apen"},
                ],
            },
            {
                "nr": "03",
                "navn": "OCA-minimering — bytt tunge moduler mot slanke FIQ-egne",
                "hvem": "ai",
                "status": "venter",
                "under": [
                    {
                        "nr": "03.01",
                        "navn": "Kandidater kartlagt; starter når plattformen er ryddet",
                        "hvem": "ai",
                        "status": "apen",
                    },
                ],
            },
        ]

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
            for t in T.search(
                [("user_ids", "in", [self.env.uid]), ("date_deadline", "!=", False)], order="date_deadline", limit=120
            ):
                if self._stage_is_done(t.stage_id if "stage_id" in f else False):
                    continue
                d = fields.Date.to_date(str(t.date_deadline)[:10])
                if d > week_end:
                    break
                row = {
                    "id": t.id,
                    "no": (t.code if "code" in f else "") or "",
                    "name": t.name or "",
                    "frist": str(d),
                    "prosjekt": t.project_id.name or "",
                    "over": d < today,
                }
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
        raw = ICP.get_param(f"fiq_gui_control.sp_urls.{comp.id}") or ICP.get_param("fiq_gui_control.sp_urls", "{}")
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
            mod = self.env["ir.module.module"].sudo().search([("name", "=", "fiq_gui_control")], limit=1)
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
            metric = self.env["ir.config_parameter"].sudo().get_param("fiq_gui_control.progress_metric", "timer")
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
            "pct": max(0, min(100, round(pct or 0))),
            "est": round(est or 0.0, 1),
            "logged": round(logged or 0.0, 1),
        }

    def _stage_is_done(self, stage):
        if not stage:
            return False
        if "fold" in stage._fields and stage.fold:
            return True
        return bool("is_closed" in stage._fields and getattr(stage, "is_closed", False))

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
                    done = sum(1 for k in kids if self._stage_is_done(k.stage_id if "stage_id" in k._fields else False))
                    return round(done * 100.0 / len(kids))
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
                return round(ordered.index(sid) * 100.0 / (len(ordered) - 1))
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
                    [("project_id", "in", ids)], ["project_id", "allocated_hours", "effective_hours"]
                )
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
    def get_avdelinger(self, company_id=False):
        """AVDELING-raden i utkast 08: «Alle · Drift · Prosjekt · Administrasjon».

        🔑 ODOO EIER BEGREPET — vi bygger ikke et FIQ-felt. Avdeling er `hr.department`,
        Odoos egen modell. Tre ganger på én uke ble det bygget et parallelt FIQ-felt for noe
        Odoo allerede eide (møtestatus `show_as`, brukerstatus `manual_im_status`, arbeidssted
        `work_location_type`) — hver gang oppdaget FØRST etter at koden var skrevet.

        🛑 MEN `hr` står IKKE i `depends` (kun `web` + `project`), og det skal den ikke:
        Kontrollrommet må virke i en base uten personalmodulen. Derfor `env.get()` + savepoint,
        samme fail-closed-mønster som oppmøte bruker for `hr.attendance` og `bus.presence`.
        Uten HR: tom liste → raden vises ikke i det hele tatt. **Ingen tom rad, ingen feilmelding
        — et filter uten valg er støy.**

        Forskjellen fra firmavelgeren er bevisst (spec 2.3): firma bestemmer HVOR du er,
        avdeling snevrer inn HVA du ser. Derfor ligger denne i innholdet, ikke i rammen.
        """
        Dep = self.env.get("hr.department")
        if Dep is None:
            return []
        out = []
        try:
            with self.env.cr.savepoint():
                domain = []
                # Firma-scope: samme regel som sidemenyen. Uten dette viser raden avdelinger
                # fra firmaer brukeren ikke står i — nøyaktig feilen `get_areas()` hadde
                # (17 treff, én ekte rot) og som ble rettet i 7.2.0.
                if company_id:
                    domain = ["|", ("company_id", "=", int(company_id)), ("company_id", "=", False)]
                for d in Dep.sudo().search(domain, order="complete_name"):
                    out.append({"id": d.id, "name": d.complete_name or d.name or ""})
        except Exception:
            # Personalmodulen finnes, men spørringen feilet (rettigheter, halvinstallert
            # modul). Filteret er pynt på forsiden — aldri verdt en hvit skjerm.
            _logger.warning(
                "FIQ control room: get_avdelinger failed — hiding the department row.",
                exc_info=True,
            )
            return []
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
            # FIRMA-SCOPE: menyen skal speile firmaet du står i, ikke alle firmaer.
            # Uten dette ga fiqas 17 toppnivå-treff der bare «012 FIQ (MP)» er en ekte
            # firma-rot — resten er maler og gamle strukturer. Menyen ble en samlepost.
            #
            # `company_id = False` tas MED: generiske/delte områder hører til alle firmaer.
            # Å utelate dem ville skjult fellesstrukturen i en flerfirma-base.
            #
            # 🛑 Dette SNEVRER INN det brukeren allerede har tilgang til — det åpner ingenting.
            # Odoos egne tilgangsregler gjelder uansett; dette er en visning, ikke en sperre.
            rot_dom = [("parent_id", "=", False), ("active", "=", True)]
            if "company_id" in P._fields:
                rot_dom.append(("company_id", "in", [self.env.company.id, False]))
            roots = P.search(rot_dom)
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
                P = self.env["project.project"]
                f = P._fields
                dom = [("parent_id", "=", parent_id)]
                if "active" in f:
                    dom.append(("active", "=", True))
                for r in P.search(dom, order="id"):
                    out.append(
                        {
                            "id": r.id,
                            "no": (r.sequence_code if "sequence_code" in f else "") or "",
                            "name": r.name or "",
                            "taskCount": (r.task_count if "task_count" in f else 0) or 0,
                        }
                    )
            elif model == "project.task":
                T = self.env["project.task"]
                f = T._fields
                for r in T.search([("parent_id", "=", parent_id)], order="id"):
                    out.append(
                        {
                            "id": r.id,
                            "no": (r.code if "code" in f else "") or "",
                            "name": r.name or "",
                        }
                    )
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
                [
                    ("model", "=", model),
                    ("res_id", "=", res_id),
                    ("message_type", "in", ["email", "comment", "notification"]),
                ],
                order="date desc",
                limit=30,
            )
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
                [("res_model", "=", model), ("res_id", "=", res_id)], order="id desc", limit=30
            )
            for a in atts:
                # mimetype + checksum → forhåndsvisning (FileViewer); ALDRI nedlasting
                out["dok"].append(
                    {
                        "id": a.id,
                        "name": a.name or _("Document"),
                        "mimetype": a.mimetype or "",
                        "checksum": a.checksum or "",
                    }
                )
        except Exception:
            pass
        return out

    @api.model
    def action_upgrade_module(self):
        """«Oppgrader» rett fra Kontrollrommet — samme som Oppgrader-knappen i Apper.
        Kontrollert løft: FIQ-admin-gruppen (eller Odoo Settings-admin) kan oppgradere
        AKKURAT denne modulen, uavhengig av tekniske innstillingsrettigheter."""
        if not (self.env.user.has_group("fiq_gui_control.group_admin") or self.env.user.has_group("base.group_system")):
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
        if not (self.env.user.has_group("fiq_gui_control.group_admin") or self.env.user.has_group("base.group_system")):
            raise AccessError(_("Only administrators can change the cockpit address."))
        url = (url or "").strip()
        if url and not url.startswith(("https://", "http://")):
            url = "https://" + url
        self.env["ir.config_parameter"].sudo().set_param("fiq_gui_control.ai_cockpit_url", url)
        return url

    # ---- «KREVER HANDLING NÅ» — globalt over hele AI-scopet (alle 0.-røttene) ----------
    @api.model
    def get_krever(self):
        """Brukerens åpne oppgaver på tvers av AI-prosjektene, m/ OPPGAVENR + PROSJEKT.
        Forsinkede først. Vises ALLTID øverst i AI KTRL."""
        out = []
        try:
            P = self.env["project.project"]
            roots = P.search([("parent_id", "=", False), ("name", "=ilike", "0.%"), ("active", "=", True)])
            if not roots:
                return out
            T = self.env["project.task"]
            f = T._fields
            today = fields.Date.context_today(self)
            for t in T.search(
                [("project_id", "child_of", roots.ids), ("user_ids", "in", [self.env.uid])],
                order="date_deadline asc",
                limit=60,
            ):
                if self._stage_is_done(t.stage_id if "stage_id" in f else False):
                    continue
                over = False
                try:
                    over = bool(t.date_deadline and fields.Date.to_date(str(t.date_deadline)[:10]) < today)
                except Exception:
                    over = False
                out.append(
                    {
                        "id": t.id,
                        "no": (t.code if "code" in f else "") or "",
                        "name": t.name or "",
                        "prosjekt": t.project_id.name or "",
                        "over": over,
                    }
                )
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
            proj = self.env["project.project"].search([("name", "ilike", "AI Økter")], limit=1)
            if not proj:
                return out
            Msg = self.env["mail.message"]
            for t in self.env["project.task"].search([("project_id", "=", proj.id)], order="id"):
                m = Msg.search(
                    [
                        ("model", "=", "project.task"),
                        ("res_id", "=", t.id),
                        ("message_type", "in", ["comment", "notification"]),
                    ],
                    order="date desc",
                    limit=1,
                )
                out.append(
                    {
                        "id": t.id,
                        "name": t.name or "",
                        "ferdig": self._stage_is_done(t.stage_id),
                        "sist": m.date.strftime("%d.%m %H:%M") if m and m.date else "",
                        "melding": html2plaintext(m.body or "").strip()[:160]
                        if m and m.body
                        else ((m.preview or "").strip()[:160] if m else ""),
                    }
                )
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
            for r in P.search(dom + [("parent_id", "=", False), ("name", "=ilike", "0.%")], order="name"):
                kunder.append({"id": r.id, "name": r.name or ""})
                ai_root_ids.append(r.id)
        pdom = dom + [("id", "child_of", ai_root_ids)] if ai_root_ids else dom + [("id", "=", 0)]
        projs = P.search(pdom, order="name")
        # AI-plattform vs interne: taggen «AI-plattform» (Coworker setter den på alt den oppretter)
        tag = self.env["project.tags"].search([("name", "=", "AI-plattform")], limit=1)
        return {
            "kunder": kunder,
            "prosjekter": [
                {
                    "id": p.id,
                    "no": (p.sequence_code if "sequence_code" in f else "") or "",
                    "name": p.name or "",
                    "ai": bool(tag and "tag_ids" in f and tag.id in p.tag_ids.ids),
                }
                for p in projs
            ],
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
            roots = (
                P.search([("parent_id", "=", False), ("name", "=ilike", "0.%"), ("active", "=", True)])
                if "parent_id" in f
                else P.browse()
            )
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
            out.append(
                {
                    "id": p.id,
                    "no": (p.sequence_code if "sequence_code" in f else "") or "",
                    "name": p.name or "",
                    "pct": pr["pct"],
                    "est": pr["est"],
                    "logged": pr["logged"],
                    "taskCount": (p.task_count if "task_count" in f else 0) or 0,
                    # Gruppering på kunde/hjerne (toppnivå-rot) ved «Alle»
                    "root_id": rt.id,
                    "root_name": rt.name or "",
                    "is_root": rt.id == p.id,
                }
            )
        return out

    # ---- AI-cockpit (fremdrifts-hub) — speiler Artifact-cockpiten mot ekte oppgaver -----
    @api.model
    def get_cockpit(self, project_id=False):
        """Cockpit-flaten i AI Kontrollrom: grupper (rotprosjekt + underprosjekter) med
        oppgaver, Du/AI-merke, status og «krever handling». Config-drevet: systemparameter
        `fiq_gui_control.cockpit_project_id` = rotprosjektets id. Defensivt/felt-guardet."""
        ICP = self.env["ir.config_parameter"].sudo()
        out = {"groups": [], "tot": {"done": 0, "pag": 0, "vent": 0, "tot": 0, "pct": 0}, "krever": [], "root": ""}
        try:
            pid = int(project_id or 0) or int(ICP.get_param("fiq_gui_control.cockpit_project_id", "0") or 0)
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
            projects += list(P.search([("parent_id", "=", root.id), ("active", "=", True)], order="id"))
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
                    over = bool(t.date_deadline and fields.Date.to_date(str(t.date_deadline)[:10]) < today)
                except Exception:
                    over = False
                rows.append(
                    {
                        "id": t.id,
                        "no": (t.code if "code" in f else "") or "",
                        "name": t.name or "",
                        "who": "du" if t.user_ids else "ai",
                        "st": st,
                        "stage": stage.name if stage else "",
                        "over": over,
                        "frist": str(t.date_deadline)[:10] if t.date_deadline else "",
                    }
                )
                out["tot"]["tot"] += 1
                out["tot"][stmap[st]] += 1
            out["groups"].append(
                {
                    "id": p.id,
                    "no": (p.sequence_code if "sequence_code" in P._fields else "") or "",
                    "name": p.name or "",
                    "done": done,
                    "total": len(rows),
                    "tasks": rows,
                }
            )
        mine = [r for g in out["groups"] for r in g["tasks"] if r["who"] == "du" and r["st"] != "ferdig"]
        mine.sort(key=lambda r: (not r["over"], r["no"]))
        out["krever"] = mine[:4]
        t = out["tot"]
        t["pct"] = round(t["done"] * 100.0 / t["tot"]) if t["tot"] else 0
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
        dom = [("project_ids", "in", t.project_id.id)] if "project_ids" in Stage._fields and t.project_id else []
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
            evs = Ev.search(
                [("partner_ids", "in", user.partner_id.ids), ("start", "<", end), ("stop", ">=", start)],
                order="start",
                limit=60,
            )
            for e in evs:
                st = fields.Datetime.context_timestamp(e, e.start) if e.start else None
                sl = fields.Datetime.context_timestamp(e, e.stop) if e.stop else None
                out["moter"].append(
                    {
                        "id": e.id,
                        "name": e.name or "",
                        # ÅRSTALL MED: «%d.%m» alene lyver så snart lista spenner over et
                        # årsskifte — «03.01» kan være i år eller for fjorten måneder siden.
                        # Samme felle Gjermund fant i Meldingssenteret. Kort år (%y) holder
                        # bredden nede uten å miste informasjonen.
                        "dato": st.strftime("%d.%m.%y") if st else "",
                        "tid": st.strftime("%H:%M") if st else "",
                        "slutt": sl.strftime("%H:%M") if sl else "",
                    }
                )
            # Måneds-markører: dager med MØTER (ikke aktiviteter)
            dager = set()
            for e in Ev.search(
                [("partner_ids", "in", user.partner_id.ids), ("start", "<", month_end), ("stop", ">=", month_start)],
                limit=300,
            ):
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
            for a in Act.search(
                [("user_id", "=", uid), ("date_deadline", "<=", end_d)], order="date_deadline", limit=30
            ):
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
                out["aktiviteter"].append(
                    {
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
                    }
                )
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
            order="name",
            limit=24,
        )

        # Batch: hvem er i et møte NÅ (calendar.event der nå ∈ [start, stop]) → partner_ids
        in_meeting = set()
        try:
            # Savepoint, ikke bare try/except: calendar/hr/bus er VALGFRIE moduler. Feiler
            # oppslaget i SQL (modul avinstallert, kolonne mangler etter halv oppgradering),
            # avbryter Postgres HELE transaksjonen — og alt lenger nede i get_presence, samt
            # alt kalleren gjør etterpå, faller med «current transaction is aborted».
            # Savepointen ruller tilbake bare dette oppslaget. Meldt av AI KR (00.04) 19.07.2026.
            with self.env.cr.savepoint():
                now = fields.Datetime.now()
                # ODOOS EGET «Vis som»-felt avgjør — ikke vår tolkning av «i møte».
                # Gjermund 20.07.2026: «native odoo har møte alternativer som skal vises».
                #
                # `show_as` (calendar/models/calendar_event.py:156, Odoo 19) = 'free' | 'busy',
                # default 'busy'. Setter brukeren et møte til «Ledig», sier hen: jeg er i møtet,
                # men kan forstyrres. Uten dette filteret gjorde ETHVERT pågående møte deg
                # utilgjengelig — også de du selv hadde merket som ledige.
                #
                # Hvorfor lese Odoos felt i stedet for å bygge vårt eget: valget virker da
                # OVERALT — her, i Odoos ledig/opptatt-visning, og mot andre som booker møter
                # med deg. Et eget FIQ-felt ville blitt en konkurrerende sannhet om samme sak.
                Event = self.env["calendar.event"].sudo()
                dom = [("start", "<=", now), ("stop", ">=", now)]
                if "show_as" in Event._fields:
                    dom.append(("show_as", "=", "busy"))
                evs = Event.search(dom)
                # Har du takket NEI til møtet, er du ikke i det.
                # `calendar.attendee.state` = 'declined' (calendar_attendee.py:28, Odoo 19).
                # Uten dette ble alle inviterte merket «i møte» — også de som avslo.
                # Deltakeren har dessuten sin EGEN ledig/opptatt-markering (`availability`,
                # calendar_attendee.py:45): arrangøren bestemmer ikke alene.
                Att = self.env["calendar.attendee"].sudo()
                har_att = "state" in Att._fields
                for e in evs:
                    if not har_att:
                        in_meeting.update(e.partner_ids.ids)
                        continue
                    for a in e.attendee_ids:
                        if a.state == "declined":
                            continue
                        if "availability" in Att._fields and a.availability == "free":
                            continue  # deltakeren har selv markert seg som ledig
                        in_meeting.add(a.partner_id.id)
                    if not e.attendee_ids:  # møte uten deltakerliste → som før
                        in_meeting.update(e.partner_ids.ids)
        except Exception:
            pass

        # Batch: hvem er FRAVÆRENDE i dag (godkjent fravær) → user_ids
        #
        # 🛑 SYKDOM VISES ALDRI — HARD REGEL (Gjermund 20.07.2026: «Meldinger som syk skal ikke
        # vises, men fraværende skal»). Samme krav i godkjent spec §13: sykdom/diagnose/årsak
        # eksponeres ALDRI som helseopplysning; kun et avledet kapasitetssignal.
        #
        # Derfor sendes KUN «fraværende i dag» videre — aldri fraværstype, aldri årsak, aldri
        # hvor lenge. Kollegaen ser at du ikke er å få tak i. Hvorfor er ikke hens sak.
        # Helseopplysninger er en særskilt kategori personopplysninger; en lekkasje her er
        # ikke en skjønnhetsfeil, den er et brudd.
        away_users = set()
        try:
            with self.env.cr.savepoint():
                Leave = self.env["hr.leave"].sudo()
                today = fields.Date.context_today(self)
                lv = Leave.search(
                    [
                        ("state", "=", "validate"),
                        ("date_from", "<=", today),
                        ("date_to", ">=", today),
                    ]
                )
                emp_ids = lv.mapped("employee_id").ids
                if emp_ids:
                    emps = self.env["hr.employee"].sudo().browse(emp_ids)
                    away_users = {x for x in emps.mapped("user_id").ids if x}
        except Exception:
            # hr_holidays er valgfri. Mangler den, er ingen markert fraværende — ikke en krasj.
            away_users = set()

        # Batch: hvem har møtt på jobb (åpen hr.attendance, ingen check_out) → user_ids
        attendance_avail = False
        checked_in_users = set()
        try:
            with self.env.cr.savepoint():
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
            with self.env.cr.savepoint():
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
            # BRUKERENS EGET VALG VINNER over det systemet gjetter seg til.
            # Gjermund 20.07.2026: man vil vise tilgjengelighet «stort sett uavhengig av hvor
            # vi er» — for forstyrrelser og for å kunne sette over telefon.
            #
            # ⭐ Odoo eier dette allerede: `manual_im_status` (mail/models/res_users.py:45) =
            # 'away' | 'busy' (= «Ikke forstyrr») | 'offline', satt av brukeren selv. Odoos egen
            # `_compute_im_status` (:111) lar det manuelle valget slå det automatiske — vi følger
            # SAMME rangering her i stedet for å bygge et konkurrerende FIQ-felt.
            # Velger brukeren «Ikke forstyrr» i Odoo, gjelder det også i Kontrollrommet.
            manuell = ""
            try:
                if "manual_im_status" in u._fields:
                    manuell = u.manual_im_status or ""
            except Exception:
                manuell = ""

            if u.id in away_users:
                # Fravær slår ALT annet: er du borte i dag, hjelper det ikke at nettleseren
                # står åpen. Uten dette sto folk på ferie som «Til stede» fordi en fane var
                # glemt oppe — og da lyver hele tavla.
                # 🛑 Kun «Fraværende». Aldri type, aldri årsak, aldri hvor lenge.
                farge, tekst = "red", _("Away")
            elif manuell == "busy":
                # «Til stede, men ikke forstyrr» — nivå 3 i godkjent spec §12.
                # Personen ER på jobb (derfor ikke rød), men har bedt om ro.
                farge, tekst = "orange", _("Do not disturb")
            elif meeting:
                farge, tekst = "orange", _("In a meeting")
            elif moett and im == "online":
                # NIVÅ 1 «Tilgjengelig»: på jobb OG ved maskinen OG ikke bedt om ro.
                # Sterkeste positive signal — det er denne du kan ringe.
                farge, tekst = "green", _("Available")
            elif moett:
                # NIVÅ 2 «Til stede»: innstemplet, men ikke aktiv ved maskinen.
                # På jobb — men kanskje ikke ved telefonen akkurat nå.
                farge, tekst = "green", _("Present")
            elif im == "online":
                farge, tekst = "green", _("Present")
            elif im == "away":
                farge, tekst = "orange", _("Out")
            elif attendance_avail:
                # 🔑 GRÅ, IKKE RØD (Gjermund 20.07, mot skjermbilde av ekte data).
                # «Ikke møtt» betyr bare at ingen har stemplet inn — det er IKKE fravær.
                # Med rødt ble tre av fire kort røde uten at noe var galt, og da slutter
                # rødt å bety noe. Rødt er nå reservert for REELT fravær (godkjent fravær).
                farge, tekst = "grey", _("Not checked in")
            else:
                # Verken oppmøte-modul, pålogging eller fravær sier noe. Vi VET ikke —
                # og da skal fargen si «ukjent», ikke «fraværende». Å påstå fravær vi ikke
                # har grunnlag for er samme feilklasse som rødt på «ikke møtt».
                farge, tekst = "grey", _("Unknown")

            name = u.name or u.login or "—"
            parts = [p for p in name.replace("-", " ").split(" ") if p]
            if len(parts) >= 2:
                initialer = (parts[0][:1] + parts[-1][:1]).upper()
            elif parts:
                initialer = parts[0][:2].upper()
            else:
                initialer = "?"
            # Bildet: hr.employee-fotoet er det «riktige» ansattbildet, men det finnes
            # bare der HR er i bruk. res.users.avatar_128 finnes alltid (Odoo faller selv
            # tilbake på et generert bilde), så den er kilden når HR-foto mangler.
            # Selve bildet sendes med — uten det kan flaten bare vise initialer.
            avatar = False
            try:
                # Savepoint: dette kjører i en løkke PER bruker. Uten den ville én feilende
                # oppslag avbrutt transaksjonen midt i, og alle gjenstående brukere falt med.
                with self.env.cr.savepoint():
                    emp = self.env["hr.employee"].sudo().search([("user_id", "=", u.id)], limit=1)
                    avatar = (emp and emp.image_128) or u.avatar_128 or False
            except Exception:
                avatar = u.avatar_128 or False
            if isinstance(avatar, bytes):
                avatar = avatar.decode()

            # MERKNAD — banner OVER navnet (Gjermund 20.07: «kan det bare være et banner
            # over navnet»). Egen linje, eget lag: den konkurrerer ALDRI med statusen om
            # samme plass. Statusen sier om du er nåbar; merknaden sier hvor du er.
            # 🛑 Merknaden endrer HVERKEN status ELLER farge — du er fortsatt tilgjengelig.
            # Er den ikke satt, finnes ikke banneret, og kortet ser ut nøyaktig som før.
            merknad, merknad_til = "", ""
            try:
                with self.env.cr.savepoint():
                    if "out_of_office_message" in u._fields and u.out_of_office_message:
                        # Feltet er HTML i Odoo; kortet skal ha ren tekst.
                        merknad = (html2plaintext(u.out_of_office_message) or "").strip()[:60]
                    if merknad and "out_of_office_to" in u._fields and u.out_of_office_to:
                        # Utløpt merknad skal IKKE vises — et banner som lyver er verre enn
                        # ingen banner. Odoo rydder ikke feltet selv (kun `is_out_of_office`
                        # beregnes), så vi filtrerer her.
                        if u.out_of_office_to < fields.Datetime.now():
                            merknad = ""
                        else:
                            merknad_til = fields.Datetime.context_timestamp(u, u.out_of_office_to).strftime("%H:%M")
            except Exception:
                merknad, merknad_til = "", ""

            # ── ARBEIDSSTED (punkt 04.04, Gjermund 20.07) ────────────────────────────
            # «Sitter du på hjemmekontor i Drøbak og sjefen vil møtes fysisk på
            # hovedkontoret, hjelper det ikke at du står som pålogget.»
            # Samme for utearbeider: anleggsplassen ER arbeidsstedet.
            #
            # ⭐ ODOO EIER DETTE ALLEREDE — ikke et parallelt FIQ-felt.
            # `hr.employee.work_location_id` + `work_location_name` + `work_location_type`
            # (hr/models/hr_employee.py:173, hr_work_location.py:15).
            # Typene er nøyaktig de Gjermund beskrev: home · office · other.
            #
            # 🛑 IKKE SPORING. Dette er stedet den ansatte selv har registrert i HR —
            # ikke en måling av hvor telefonen befinner seg. Frivillig, gjenkallbart,
            # og allerede synlig i Odoo for den som har tilgang. Vi VISER det, samler
            # det ikke inn. GPS-sporing er en annen sak med langt høyere terskel.
            sted, sted_type = "", ""
            try:
                with self.env.cr.savepoint():
                    emp = self.env["hr.employee"].sudo().search([("user_id", "=", u.id)], limit=1)
                    if emp and "work_location_name" in emp._fields:
                        sted = (emp.work_location_name or "")[:40]
                    if emp and "work_location_type" in emp._fields:
                        sted_type = emp.work_location_type or ""
            except Exception:
                # hr er valgfri, og feltene kom i ulike versjoner. Mangler de, vises
                # ingen sted — ikke en krasj.
                sted, sted_type = "", ""

            out.append(
                {
                    "id": u.id,
                    "partner_id": u.partner_id.id,
                    "navn": name,
                    "merknad": merknad,
                    "merknad_til": merknad_til,
                    "sted": sted,
                    "sted_type": sted_type,
                    "er_meg": u.id == self.env.uid,
                    "initialer": initialer,
                    "status": im,  # bakoverkomp (dot)
                    "farge": farge,  # green | orange | red – farger HELE kortet
                    "tekst": tekst,  # Til stede | I møte | Ute | Fraværende | Ikke møtt
                    "has_photo": bool(avatar),
                    "avatar": (f"data:image/png;base64,{avatar}") if avatar else False,
                }
            )
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
            # 🔴 INNBOKSEN HAR TO KILDER — 0.1 E-post og 0.2 AI-meldinger. Ikke flere.
            #
            # Gjermund 23.07, mot skjermbildet: «tasks og aktiviteter skal ikke ligge der,
            # og de to som skal ligge der er ikke koblet.» To ordrer i én setning:
            #
            # 🛑 1) «oppgaver» og «aktiviteter» FJERNET — begge nøklene, ikke bare menypunktene.
            #    «oppgaver» pekte på `project.action_view_task` og «aktiviteter» på
            #    `mail.mail_activity_action` — begge Odoos EGNE lister. De var derfor de eneste
            #    innboks-punktene som åpnet noe, fordi de forlot Kontrollrommet og landet på noe
            #    Odoo alltid har installert.
            #    🔑 Lærdommen er ikke «feil handling», men RETNING: innboksen skal vise det som
            #    kommer INN til deg i FIQ. Oppgaver og aktiviteter er noe du ARBEIDER med, og de
            #    har sine egne flater. At de virket skjulte at resten manglet kobling — de
            #    fungerende punktene var kamuflasjen.
            #    Nøkkelen fjernes HELT: en ledig nøkkel i denne tabellen blir tatt i bruk igjen
            #    av neste økt som leter etter «noe som finnes fra før».
            #
            # 🔑 2) «de to som skal ligge der er ikke koblet» — MÅLT 23.07, og det er PORT 0,
            #    ikke en kodefeil. Begge handlingene under FINNES i koden (verifisert mot
            #    `action_fiq_gui_epost` og `action_fiq_ai_kr` i deres egne moduler). De faller
            #    til «under utvikling» fordi `env.ref()` gir False når modulen ikke er
            #    INSTALLERT i basen — og hos Gjermund står bare fem av tjuefem moduler.
            #    🛑 Derfor er koden her IKKE endret for disse to. Å «fikse» en kobling som
            #    allerede er riktig, ville lagt en ny feil oppå en installasjonssak.
            "epost": "fiq_gui_epost.action_fiq_gui_epost",
            "ai": "fiq_gui_ai_kr.action_fiq_ai_kr",
            # De andre kontrollpanelene (fiq_gui_*-flatene) — vises i Styring-menyen når installert
            "gui_prj": "fiq_gui_prj.action_fiq_gui_prj",
            "gui_crm": "fiq_gui_crm.action_fiq_gui_crm",
            "gui_leads": "fiq_gui_crm_leads.action_fiq_gui_crm_leads",
            "gui_so": "fiq_gui_crm_so.action_fiq_gui_crm_so",
            # Beholdt for oppslag, men IKKE et menypunkt lenger: e-post er en kanal inne i
            # Kommunikasjon, ikke et eget toppnivå (Gjermund 17.07.2026).
            "gui_epost": "fiq_gui_epost.action_fiq_gui_epost",
            "gui_rgs": "fiq_gui_rgs.action_fiq_gui_rgs",
            # 18.07.2026: KR tegnet sine EGNE gamle utgaver av disse (view: kommunikasjon/
            # airmm/prosjektkr) i stedet for de ekte modulene. Modulene var installert og
            # oppdaterte hele tiden — menyen pekte bare aldri paa dem. Verifisert i basen:
            # alle tre handlingene finnes i ir_model_data.
            "kommunikasjon": "fiq_gui_comm.action_fiq_gui_comm",
            "airmm": "fiq_gui_ai_kr.action_fiq_ai_kr",
            # «Styring» — AI KRs egen flate (fiq_gui_ai_kr 19.0.3.0.0, bedt om 23.07).
            # 🔑 Merk: AI KR registrerer seg BEVISST ikke i `fiq_gui_flates`. Gjermund
            # 22.07: «feil ramme — den skal bruke AI KR sin ramme.» Skall-registrering
            # ville gjort flaten til innmat i KRs ramme. For dem gjelder to lag, ikke tre,
            # og `doAction` er DA riktig vei — ikke en mangel.
            "ai_styring": "fiq_gui_ai_kr.action_fiq_ai_styring",
            "gui_fin": "fiq_gui_fin.action_fiq_gui_fin",
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
            internal = bool(m.author_id and m.author_id.user_ids and any(not u.share for u in m.author_id.user_ids))
            is_email = m.message_type == "email"
            out.append(
                {
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
                }
            )
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
    _DASHBOARD_CANDIDATES: ClassVar[list] = [
        ("spreadsheet_dashboard.ir_actions_dashboard_action", "Dashboards (Odoo)"),
        ("sale.action_order_report_all", "Sales analysis"),
        ("account.action_account_invoice_report_all", "Invoice analysis"),
        ("purchase.action_purchase_order_report_all", "Purchase analysis"),
        ("crm.crm_opportunity_report_action", "Pipeline analysis"),
        ("hr_timesheet.timesheet_action_report_by_project", "Timesheet analysis"),
    ]

    @api.model
    def get_fiq_flater(self):
        """Every FIQ module that WANTS a spot in the control room menu, discovered — not hardcoded.

        A module registers itself by shipping ONE ir.config_parameter:

            fiq_gui_control.flate.<key> = {"label": "Inspections", "xmlid": "fiq_befaring.action_fiq_befaring",
                                           "sequence": 60, "icon": "/mod/static/img/x.png",
                                           "groups": ["fiq_gui_control.group_manager"]}

        Optional "groups": only users in at least one of those groups see the flate. Omit it and the
        flate is visible to everyone with control room access. This is TIDINESS, not security — the
        real gate is the action's own access rules; hiding a menu item never grants or denies access.

        Why this exists: the menu used to be a hardcoded list inside control_room.js, so EVERY new
        module required editing the control room core and bumping its version. Modules shipped, worked,
        had actions — and stayed invisible. Discovery removes that coupling: the module declares, the
        control room finds it. Nothing here needs to change when module number 30 arrives.

        Safety: the action xmlid must resolve in THIS database (env.ref guard) or the entry is dropped,
        so a menu item can never point at something the tenant doesn't have.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        prefix = "fiq_gui_control.flate."
        out = []
        for param in ICP.search([("key", "=like", prefix + "%")]):
            key = param.key[len(prefix) :]
            if not key:
                continue
            try:
                spec = json.loads(param.value or "{}")
            except (ValueError, TypeError):
                # A malformed declaration must never break the menu for everyone — but it
                # must not vanish silently either: a typo used to produce a flate that never
                # appeared, with nothing in the log to explain why. Reported by AI KR 18.07.2026.
                _logger.warning(
                    "FIQ control room: skipping flate %r — its ir.config_parameter %r is not "
                    'valid JSON. Expected {"label": ..., "xmlid": ..., "sequence": ...}.',
                    key,
                    param.key,
                )
                continue
            xmlid = spec.get("xmlid")
            if not xmlid:
                _logger.warning(
                    "FIQ control room: skipping flate %r — no 'xmlid' in %r. The entry cannot "
                    "open anything without one.",
                    key,
                    param.key,
                )
                continue
            if not self.env.ref(xmlid, raise_if_not_found=False):
                # Legitimate on a tenant without that module — but it is also what a typo in
                # the xmlid looks like, so say which one was dropped.
                _logger.info(
                    "FIQ control room: skipping flate %r — action %r does not exist in this "
                    "database (module not installed, or the xmlid is misspelled).",
                    key,
                    xmlid,
                )
                continue
            # Group gate (layer 1). Decided SERVER-side from the session's own user — never from
            # anything the client sends. A malformed 'groups' hides the flate rather than exposing
            # it: fail-closed, the same rule as har_000_rettighet().
            groups = spec.get("groups") or []
            if groups:
                try:
                    if not any(self.env.user.has_group(g) for g in groups):
                        continue
                except Exception:
                    _logger.warning(
                        "FIQ control room: hiding flate %r — its 'groups' could not be evaluated "
                        "(%r). Fail-closed: hidden rather than shown.",
                        key,
                        groups,
                    )
                    continue
            out.append(
                {
                    "key": key,
                    "label": self._flate_label(spec, key),
                    "xmlid": xmlid,
                    "icon": spec.get("icon") or False,
                    "sequence": int(spec.get("sequence") or 50),
                }
            )
        # Layer 2: the user's own choice, on top of what layer 1 already allowed. «Sy ditt eget KR.»
        #
        # The order matters and is not negotiable: layer 1 (groups, above) decides what the user MAY
        # see; this only decides what she WANTS to see among those. A stored preference can hide a
        # flate, never reveal one — so a stale preference for a flate she has lost access to simply
        # has nothing to act on. Client input can only narrow, never widen.
        skjulte = self._skjulte_flater()
        for f in out:
            f["skjult"] = f["key"] in skjulte
        return sorted(out, key=lambda f: (f["sequence"], f["label"]))

    @api.model
    def get_kr_bokser(self, company_id=False):
        """One summary box per flate for the control room front page.

        Each flate owns its own numbers: the control room asks the flate's data model for them and
        does not know how they are computed. Contract — the flate ships a model named
        `fiq.gui.<key>.data` (same <key> as in its self-registration) with:

            def get_kr_boks(self, company_id=False)
                -> {"haster": int, "i_dag": int, "totalt": int,
                    "linjer": [{"tekst": str, "res_id": int}, ...]}

        A flate without that model or method simply has no box — no empty placeholders, no noise.
        A flate whose box raises is skipped and logged; one broken module must never take down the
        front page for everything else.

        Respects the same two layers as the menu: only flates the user may see (groups) and has not
        switched off (her own choice) are asked at all.
        """
        out = []
        for flate in self.get_fiq_flater():
            if flate.get("skjult"):
                continue
            model_name = "fiq.gui.{}.data".format(flate["key"])
            Model = self.env.get(model_name)
            if Model is None or not hasattr(Model, "get_kr_boks"):
                continue
            try:
                # SAVEPOINT PER FLATE — ikke bare try/except.
                #
                # PostgreSQL avbryter HELE transaksjonen ved en SQL-feil. Et bare `except`
                # fanger unntaket, men transaksjonen er allerede død: hvert påfølgende kall
                # feiler med «current transaction is aborted», og ÉN ødelagt flate tar ned
                # hele forsiden. Savepointen ruller tilbake bare denne flatens arbeid, så
                # resten kan spørres videre. Meldt av AI KR (00.04) 19.07.2026 etter at
                # nøyaktig dette slo ut i deres modul: én SQL-feil felte fire urelaterte
                # metoder. Core bruker samme mønster (account/models/chart_template.py:248).
                with self.env.cr.savepoint():
                    boks = Model.get_kr_boks(company_id=company_id)
            except Exception:
                # Deliberately broad: a flate's box is decoration on the front page, never worth
                # a white screen. Logged with the module name so the owner can find it.
                _logger.warning(
                    "FIQ control room: box for flate %r failed (%s.get_kr_boks) — skipping it.",
                    flate["key"],
                    model_name,
                    exc_info=True,
                )
                continue
            if not boks:
                continue
            out.append(
                {
                    "key": flate["key"],
                    "label": flate["label"],
                    "xmlid": flate["xmlid"],
                    "icon": flate.get("icon") or False,
                    "sequence": flate["sequence"],
                    "haster": int(boks.get("haster") or 0),
                    "i_dag": int(boks.get("i_dag") or 0),
                    "totalt": int(boks.get("totalt") or 0),
                    # Ro-budsjett: tall og korte linjer, aldri varsler som maser.
                    "linjer": (boks.get("linjer") or [])[:5],
                }
            )
        return out

    # =====================================================================
    #  Fold/utvid — ÉN oppførsel for alle flater
    #
    #  Målt 19.07.2026: vi hadde SEKS ulike kollaps-implementasjoner (cpFold, cpDiagFold,
    #  aktGrpFold, collapsed, treeClosed i control_room.js + foldet i prj.js), og bare ÉN
    #  av dem husket noe. Samme handling oppførte seg ulikt avhengig av hvor brukeren sto —
    #  samme klasse feil som `view:`-fella. Gjermund 19.07: «generell kollapse og utvide på
    #  alle nivåer». Flatene kaller disse i stedet for å skrive sin egen sjuende variant.
    #
    #  To nivåer med BEVISST ulik logikk (fra PRJ-fasiten, 00.03 — «ikke rydd den bort»):
    #    · «Fold alt» / «Utvid alt» = EKSPLISITT. Samme resultat hver gang, uansett tilstand.
    #    · Klikk på én overskrift    = VEKSLENDE. Viser tilstanden der du står.
    # =====================================================================

    def _fold_nokkel(self, node):
        """En stabil fold-nøkkel for én rad.

        🛑 ALLTID ID, ALDRI NAVN. «H0101» går igjen på tvers av blokker, mappenavn gjentas i
        Kommunikasjon, kontonavn i Finans — folder du på navn, folder du feil rader et helt
        annet sted i treet. Fella er verifisert av PRJ (00.03).
        """
        if isinstance(node, dict):
            node = node.get("id")
        return str(node)

    @api.model
    def get_fold_state(self, omraade):
        """Which rows this user has folded in `omraade`, as a list of keys."""
        rec = self._get_or_create_current()
        try:
            alle = json.loads(rec.fold_state or "{}")
        except (ValueError, TypeError):
            # A corrupt preference must never break a view: everything shows, nothing is lost.
            _logger.warning(
                "FIQ control room: fold_state for user %s is not valid JSON — treating as empty.", self.env.uid
            )
            return []
        return list(alle.get(omraade) or [])

    @api.model
    def set_fold(self, omraade, node, foldet):
        """Fold or unfold ONE row. Toggling is the caller's business — this stores a fact.

        Returns the area's new key list so the client never has to guess what was stored.
        """
        rec = self._get_or_create_current()
        try:
            alle = json.loads(rec.fold_state or "{}")
        except (ValueError, TypeError):
            alle = {}
        nokler = set(alle.get(omraade) or [])
        n = self._fold_nokkel(node)
        if foldet:
            nokler.add(n)
        else:
            nokler.discard(n)
        alle[omraade] = sorted(nokler)
        rec.fold_state = json.dumps(alle)
        return alle[omraade]

    @api.model
    def set_fold_alle(self, omraade, noder, foldet):
        """«Fold alt» / «Utvid alt» — explicit, not a toggle.

        Verified 19.07.2026 that no such control existed anywhere in the 24 modules; this is the
        only place it lives now. `noder` is what the flate currently shows, so folding all only
        touches the rows in front of the user — not rows she filtered away.
        """
        rec = self._get_or_create_current()
        try:
            alle = json.loads(rec.fold_state or "{}")
        except (ValueError, TypeError):
            alle = {}
        alle[omraade] = sorted({self._fold_nokkel(n) for n in (noder or [])}) if foldet else []
        rec.fold_state = json.dumps(alle)
        return alle[omraade]

    def _flate_label(self, spec, key):
        """The flate's menu label in the user's language.

        Reported by Finans (2.70) 19.07.2026: the control room menu was English for ALL eleven
        flates («Accounting» in the control room, «Regnskap» in Odoo's own menu — same flate, two
        names). The label came straight out of ir.config_parameter and was returned raw.

        Why .po files cannot fix this: ir.config_parameter.value is a plain string, not a
        translatable field — gettext never sees it. (And in Odoo 19 there is no ir_translation
        table to fall back on; translations live as JSON inside the field itself. Verified:
        information_schema has 0 rows for ir_translation.)

        Two ways in, so no flate is forced to change:
          "label": "Accounting"                              → looked up in OUR translations
          "label": {"en_US": "Accounting", "nb_NO": "Regnskap"}  → the module owns its own name

        The dict form is the right one long-term: each flate owns what it is called, rather than
        the control room translating everyone else's words. Both keep working.
        """
        label = spec.get("label")
        if isinstance(label, dict):
            # Module ships its own translations. Fall back user's language → NORWEGIAN → English
            # → any value, so a missing translation shows a real name rather than an empty entry.
            #
            # Norwegian before English is deliberate (Gjermund 19.07.2026, [[norsk-spraklinje-er-fasit]]):
            # nb_NO is the main language in every company and every Odoo database, and the English
            # line is often a stale string nobody has touched in years. Falling back to it would
            # show an outdated name as if it were current.
            lang = self.env.lang or "nb_NO"
            return label.get(lang) or label.get("nb_NO") or label.get("en_US") or next(iter(label.values()), key)
        if label:
            # Plain string: run it through gettext so labels listed in our own i18n/*.po translate.
            #
            # ⚠️ BEVISST, MEN SKJØRT — les dette før noen «rydder» her.
            # `_()` med en VARIABEL kan ikke leses av gettext-uttrekkeren: den skanner kildekoden
            # etter `_("fast tekst")` og finner ingenting her. Oversettelsen virker derfor KUN
            # hvis strengen tilfeldigvis alt står i `i18n/*.po` fra et annet sted.
            # ✅ Målt 24.07.2026: alle fem registrerte etikettene — «Inspections», «Deviations»,
            #    «Timeline», «AI roles», «Message routing» — ligger i nb_NO.po. Det VIRKER i dag.
            # 🛑 Men en ny modul som registrerer seg med en NY etikett får den ikke oversatt, og
            #    ingenting varsler: teksten står bare på engelsk. En stille mangel, ikke en feil.
            # 👉 Den varige løsningen er dict-formen over (`{"en_US": …, "nb_NO": …}`), der modulen
            #    eier sine egne oversettelser. Denne grenen er ren bakoverkompatibilitet.
            return _(label)
        return key.replace("_", " ").title()

    def _skjulte_flater(self):
        """Flate keys this user has switched off, as a set. Stored per user+company."""
        rec = self._get_or_create_current()
        raw = rec.skjulte_flater or ""
        return {k.strip() for k in raw.split(",") if k.strip()}

    @api.model
    def set_flate_synlig(self, key, synlig):
        """Turn one flate on or off for the current user. Returns the new hidden set.

        Only ever writes to this user's own row — a user cannot change what anyone else sees, and
        cannot grant herself a flate: hiding is subtraction only (see get_fiq_flater, layer 2).
        """
        rec = self._get_or_create_current()
        skjulte = self._skjulte_flater()
        if synlig:
            skjulte.discard(key)
        else:
            skjulte.add(key)
        rec.skjulte_flater = ",".join(sorted(skjulte))
        return sorted(skjulte)

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

    # ── MERKNAD PÅ EGET OPPMØTEKORT: «Lunsj» + fritekst (Gjermund 20.07.2026) ──────────
    #
    # Gjermunds bestilling, presisert i tre runder — presiseringene ER kravet:
    # 1. «Lunsj er ikke et møte, og er i norske forhold ikke et fast tidspunkt.»
    #    🛑 Odoo deler dagen i to arbeidsøkter med et hull imellom — bygget for land der
    #    lunsj er en lang, fast pause. I Norge er den kort og tas når det passer.
    #    👉 Vi rører derfor ALDRI arbeidstidskalenderen (`resource.calendar`). Merknaden er
    #    en OPPLYSNING, ikke en pause som trekkes fra.
    # 2. «De aller fleste må være tilgjengelig i lunsjen for henvendelser og telefoner.»
    #    👉 Merknaden endrer IKKE status og IKKE farge. Du står fortsatt tilgjengelig.
    #    Dette er ikke «Ikke forstyrr» — det er noe helt annet, og må ikke blandes.
    # 3. «Jeg ønsker bare at det er anmerket, og at det er mulig å vise hensyn.»
    #    👉 En kollega kan velge å vente ti minutter hvis saken ikke haster — men skal
    #    fortsatt kunne ringe hvis den gjør det. Anmerkning, aldri sperre.
    #
    # ⭐ ODOOS EGNE FELT — ikke et parallelt FIQ-felt (mail/models/res_users.py:39-41):
    #   `out_of_office_from` (datetime) · `out_of_office_to` (datetime) · `out_of_office_message` (html)
    # Odoo utløper det SELV når «til» passeres (`_compute_is_out_of_office`, :97) — vi trenger
    # ingen bakgrunnsjobb for at lunsjen skal gå ut av seg selv.
    #
    # Lunsj = fritekst med ferdig utfylt tekst og 40 min som forslag (Gjermunds tall).
    # ÉN mekanisme, to knapper — ikke to systemer som må holdes i synk.
    # ── FERIE SLÅR AV POSISJONSDELING (Gjermund 20.07, punkt 04.06) ───────────────────
    #
    # «Er en ansatt på ferie skal GPS kunne slås av — enten automatisk eller ved valg av
    #  brukeren — eller slås på av brukeren.» Presisert: automatisk ved ferie, brukeren
    #  varsles, og kan bevisst la den stå.
    #
    # 🔑 Kjøres ved OPPSLAG, ikke som bakgrunnsjobb. En jobb som går én gang i døgnet
    # ville latt posisjonen stå på i timevis etter at ferien startet — og en bryter som
    # slår av «snart» er ikke en bryter man kan stole på.
    #
    # 🛑 Slår ALDRI på igjen automatisk. Har brukeren bevisst skrudd den på under ferien,
    # skal systemet ikke overstyre det ved neste oppslag. Automatikk som overkjører et
    # menneskelig valg er verre enn ingen automatikk.
    def _ferie_slar_av_posisjon(self):
        """Slå av posisjonsdeling hvis brukeren har godkjent fravær som gjelder nå.

        Returnerer True hvis den nettopp ble slått av (→ brukeren skal varsles).
        """
        self.ensure_one()
        if not self.del_posisjon:
            return False
        try:
            with self.env.cr.savepoint():
                today = fields.Date.context_today(self)
                emp = self.env["hr.employee"].sudo().search([("user_id", "=", self.user_id.id)], limit=1)
                if not emp:
                    return False
                paa_ferie = (
                    self.env["hr.leave"]
                    .sudo()
                    .search_count(
                        [
                            ("employee_id", "=", emp.id),
                            ("state", "=", "validate"),
                            ("date_from", "<=", today),
                            ("date_to", ">=", today),
                        ]
                    )
                )
        except Exception:
            # hr_holidays er valgfri — mangler den, er ingen på ferie. Ikke en krasj.
            return False
        if not paa_ferie:
            return False
        self.sudo().write({"del_posisjon": False, "del_posisjon_auto_av": True})
        return True

    @api.model
    def sett_posisjonsdeling(self, paa):
        """Brukerens EGEN bryter. Slår hen den på igjen under ferie, respekteres det.

        🛑 KUN egen bruker — ingen kan endre en kollegas deling.
        """
        rec = self._get_or_create_current()
        rec.sudo().write(
            {
                "del_posisjon": bool(paa),
                # Nullstill varselet: har brukeren tatt stilling, skal hen ikke få beskjed
                # om det samme igjen. Et varsel som gjentar seg blir støy og leses ikke.
                "del_posisjon_auto_av": False,
            }
        )
        return {"paa": bool(paa)}

    @api.model
    def sett_min_merknad(self, tekst=False, minutter=False, slutt=False):
        """Sett merknaden på MITT eget oppmøtekort. Tom tekst = fjern merknaden.

        `minutter` gir tilbake-tid fra nå (lunsj: 40). `slutt` gir et eksakt tidspunkt
        («HH:MM» eller ISO) og vinner over `minutter` — brukeren kan overstyre forslaget.
        🛑 KUN egen bruker. Ingen kan sette merknad på en kollega.
        """
        bruker = self.env.user
        felt = bruker._fields

        # Fjern merknaden: brukeren er tilbake.
        if not tekst:
            vals = {}
            for f in ("out_of_office_from", "out_of_office_to", "out_of_office_message"):
                if f in felt:
                    vals[f] = False
            if vals:
                bruker.sudo().write(vals)  # sudo: skriver KUN på seg selv, felt over
            return {"tekst": "", "til": ""}

        if "out_of_office_message" not in felt:
            # Odoos felt mangler (mail ikke installert) — si det ærlig, ikke feil stille.
            return {"feil": "mangler_felt"}

        naa = fields.Datetime.now()
        til = False
        if slutt:
            try:
                s = str(slutt).strip()
                if len(s) == 5 and ":" in s:  # «HH:MM» → i dag, brukerens tidssone
                    t = datetime.strptime(s, "%H:%M").time()
                    lokal = fields.Datetime.context_timestamp(bruker, naa)
                    kandidat = lokal.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)
                    # Er klokkeslettet passert i dag, mente brukeren i morgen.
                    if kandidat <= lokal:
                        kandidat += timedelta(days=1)
                    til = kandidat.astimezone(pytz.UTC).replace(tzinfo=None)
                else:
                    til = fields.Datetime.to_datetime(s)
            except Exception:
                til = False  # ugyldig tid → fall til `minutter`
        if not til and minutter:
            try:
                til = naa + timedelta(minutes=int(minutter))
            except (ValueError, TypeError):
                til = False

        vals = {"out_of_office_message": tekst}
        if "out_of_office_from" in felt:
            vals["out_of_office_from"] = naa
        if "out_of_office_to" in felt:
            # Uten «til» blir merknaden stående til brukeren fjerner den selv. Odoo
            # tillater det (:100), men da lyver kortet hvis noen glemmer det. Derfor
            # er en tilbake-tid alltid foreslått i grensesnittet.
            vals["out_of_office_to"] = til or False
        bruker.sudo().write(vals)
        return {
            "tekst": tekst,
            "til": fields.Datetime.context_timestamp(bruker, til).strftime("%H:%M") if til else "",
        }

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

    # =========================================================================
    #  KR-LISTER — de fire datadrevne seksjonene fra utkast 15
    #  Eier: B-sporet (19.0.7.11.x). Kalles av kr_lister.js.
    #
    #  🔑 HVORFOR EGNE METODER OG IKKE `get_kr_bokser`:
    #  Boks-kontrakten leverer linjer som {"tekst": str, "res_id": int} — ÉN ferdig
    #  sammensatt setning per linje. Fasiten
    #  (`docs/mockups/0.00 IQ kontrollrom_utkast15_2026-07-20.html`, linje 817-851,
    #  lest i kilden 23.07 — ikke gjenfortalt) krever FIRE ADSKILTE kolonner per rad:
    #  kilde-etikett · dokumentnr · beskrivelse · alder/tid til høyre.
    #  De kolonnene finnes ikke i `tekst`; de er allerede smeltet sammen til én streng.
    #  Å plukke dem ut igjen med regex ville vært gjetning på en ANNEN flates
    #  formatering — og den formateringen kan endres uten at vi får vite det.
    #  👉 Derfor spør vi modellene direkte og lar hver flate beholde sin egen boks.
    #
    #  🛑 SAVEPOINT PER KILDE — ikke bare try/except. PostgreSQL avbryter HELE
    #  transaksjonen ved en SQL-feil; et bart `except` gir «current transaction is
    #  aborted» på alt som kommer etterpå, og ÉN ødelagt kilde tar ned hele forsiden.
    #  Samme mønster som `get_kr_bokser` og core (account/models/chart_template.py:248).
    # =========================================================================

    def _kr_kilde_etikett(self, kode):
        """Kilde-etikettene i fasiten («Finans», «Regnskap», «Kommunikasjon» …).

        Kildespråk er engelsk, nb_NO er oversettelse — derfor `_()` og aldri en
        hardkodet norsk streng.
        """
        return {
            "fin": _("Finance"),
            "rgs": _("Accounting"),
            "comm": _("Communication"),
            "prj": _("Projects"),
            "salg": _("Sales"),
        }.get(kode, kode)

    def _kr_maaned_navn(self, mnd):
        """Månedsnavn 1-12, oversettbart.

        🛑 Vi bruker IKKE `strftime("%B")`: den følger serverens locale, ikke brukerens
        språk. Da ville en norsk bruker fått «May 2026» fordi serveren står på C-locale
        — en stille feil som først synes i grensesnittet.
        """
        return [
            _("January"),
            _("February"),
            _("March"),
            _("April"),
            _("May"),
            _("June"),
            _("July"),
            _("August"),
            _("September"),
            _("October"),
            _("November"),
            _("December"),
        ][mnd - 1]

    def _kr_tid_tekst(self, naa, tidspunkt):
        """«i dag 08:41» · «i går 16:03» · «18.07.2026» — fasitens tre former.

        🛑 ALLTID ÅRSTALL på den absolutte formen (`%d.%m.%Y`). En dato uten år er en
        felle Gjermund har funnet to ganger — «18.07» kan være hvilket som helst år.
        """
        if not tidspunkt:
            return ""
        lokal = fields.Datetime.context_timestamp(self, tidspunkt)
        i_dag = naa.date()
        d = lokal.date()
        if d == i_dag:
            return _("today %s") % lokal.strftime("%H:%M")
        if d == i_dag - timedelta(days=1):
            return _("yesterday %s") % lokal.strftime("%H:%M")
        return lokal.strftime("%d.%m.%Y")

    @api.model
    def get_kr_krever_handling(self, company_id=False, grense=12):
        """Seksjon 1 — «Krever handling — på tvers av rom». ÉN RAD PER SAK.

        Fasit (utkast 15, linje 817-822): Finans og Regnskap gir én rad per faktura med
        dokumentnr + motpart + alder i dager. Kommunikasjon gir ÉN SAMLERAD
        («7 meldinger uten svar — eldste 4 dager») fordi ubesvart post ikke har et
        dokumentnummer. Den forskjellen er fasitens, ikke min forenkling.

        Dagens `get handlingsposter()` i control_room.js gir 2 samlekategorier; dette
        er raden-per-sak den mangler.

        Returnerer {"totalt": int, "rader": [{kilde, kode, tekst, naar, model, res_id}]}.
        `totalt` er antall saker — tallet som står i overskriften (5 i fasiten).
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        rader = []

        # --- Finans + Regnskap: forfalte, bokførte fakturaer ------------------
        # Begge leser account.move. Skillet i fasiten er hvilken FLATE saken hører
        # til (kundefaktura = Finans 2.70, leverandørfaktura = Regnskap 2.80),
        # ikke to ulike tabeller.
        try:
            with selv.env.cr.savepoint():
                Move = selv.env["account.move"]
                forfalte = Move.search_read(
                    [
                        ("move_type", "in", ("out_invoice", "in_invoice", "out_refund", "in_refund")),
                        ("state", "=", "posted"),
                        ("payment_state", "in", ("not_paid", "partial")),
                        ("invoice_date_due", "<", i_dag),
                    ],
                    ["name", "partner_id", "invoice_date_due", "move_type"],
                    order="invoice_date_due asc",
                    limit=grense,
                )
                for m in forfalte:
                    dager = (i_dag - m["invoice_date_due"]).days if m["invoice_date_due"] else 0
                    kode = "fin" if m["move_type"] in ("out_invoice", "out_refund") else "rgs"
                    rader.append(
                        {
                            "kilde": selv._kr_kilde_etikett(kode),
                            "kode": m["name"] or "—",
                            "tekst": m["partner_id"][1] if m["partner_id"] else "—",
                            "naar": _("%s days") % dager,
                            "sort": dager,
                            "model": "account.move",
                            "res_id": m["id"],
                        }
                    )
        except Exception:
            _logger.warning(
                "FIQ KR-lister: «krever handling» — Finans/Regnskap feilet, hopper over "
                "den kilden. Resten av seksjonen vises.",
                exc_info=True,
            )

        # --- Kommunikasjon: ÉN samlerad, slik fasiten viser den ---------------
        try:
            with selv.env.cr.savepoint():
                DATA = "fiq.meldingssenter.data"
                if DATA in selv.env:
                    meldinger = (
                        selv.env[DATA].get_messages(boks="uleste", firm=company_id or False, period="alle") or []
                    )
                    if meldinger:
                        naa_dt = fields.Datetime.now()
                        eldste_dager = 0
                        for m in meldinger:
                            raa = m.get("dato") or m.get("date")
                            if not raa:
                                continue
                            try:
                                d = fields.Datetime.to_datetime(raa)
                            except (ValueError, TypeError):
                                # En melding med ubrukelig dato skal ikke felle raden.
                                continue
                            if d:
                                eldste_dager = max(eldste_dager, (naa_dt - d).days)
                        rader.append(
                            {
                                "kilde": selv._kr_kilde_etikett("comm"),
                                "kode": "—",
                                "tekst": _("%s messages awaiting reply") % len(meldinger),
                                "naar": _("oldest %s days") % eldste_dager,
                                "sort": eldste_dager,
                                "model": False,
                                "res_id": False,
                            }
                        )
        except Exception:
            _logger.warning(
                "FIQ KR-lister: «krever handling» — Kommunikasjon feilet, hopper over den kilden.", exc_info=True
            )

        # Eldst først: i denne seksjonen ER alder hastegraden.
        rader.sort(key=lambda r: r["sort"], reverse=True)
        for r in rader:
            r.pop("sort", None)
        return {"totalt": len(rader), "rader": rader[:grense]}

    @api.model
    def get_kr_siste_aktivitet(self, company_id=False, grense=12):
        """Seksjon 2 — «Siste aktivitet». 12 rader på tvers av flatene.

        Fasit (utkast 15, linje 830-838): modul-etikett · nr · tekst · tid til høyre.
        Nummeret er flatens EGET saksnummer der det finnes (`T0412`, `INV/2025/00009`),
        ellers «—». Vi finner aldri opp et nummer.

        🔑 Oppgavenummeret er `code` (STABILT), ikke WBS (dynamisk) — de skal aldri
        blandes. Feltet finnes bare når fiq_gui_prj er installert, derfor sjekkes
        `_fields` før det spørres om.
        """
        selv = self.with_company(company_id) if company_id else self
        naa = fields.Datetime.context_timestamp(selv, fields.Datetime.now())
        rader = []

        # --- Prosjekt: sist endrede oppgaver ----------------------------------
        try:
            with selv.env.cr.savepoint():
                Task = selv.env["project.task"]
                felter = ["name", "write_date"]
                if "code" in Task._fields:
                    felter.append("code")
                for r in Task.search_read([], felter, order="write_date desc", limit=grense):
                    rader.append(
                        {
                            "kilde": selv._kr_kilde_etikett("prj"),
                            "kode": r.get("code") or "—",
                            "tekst": r.get("name") or "—",
                            "naar": selv._kr_tid_tekst(naa, r.get("write_date")),
                            "sort": r.get("write_date") or False,
                            "model": "project.task",
                            "res_id": r["id"],
                        }
                    )
        except Exception:
            _logger.warning("FIQ KR-lister: «siste aktivitet» — Prosjekt feilet.", exc_info=True)

        # --- Finans + Regnskap: sist bokførte fakturaer -----------------------
        try:
            with selv.env.cr.savepoint():
                rows = selv.env["account.move"].search_read(
                    [("state", "=", "posted")],
                    ["name", "partner_id", "write_date", "move_type"],
                    order="write_date desc",
                    limit=grense,
                )
                for r in rows:
                    kode = "fin" if r["move_type"] in ("out_invoice", "out_refund") else "rgs"
                    rader.append(
                        {
                            "kilde": selv._kr_kilde_etikett(kode),
                            "kode": r["name"] or "—",
                            "tekst": r["partner_id"][1] if r["partner_id"] else "—",
                            "naar": selv._kr_tid_tekst(naa, r["write_date"]),
                            "sort": r["write_date"] or False,
                            "model": "account.move",
                            "res_id": r["id"],
                        }
                    )
        except Exception:
            _logger.warning("FIQ KR-lister: «siste aktivitet» — Finans/Regnskap feilet.", exc_info=True)

        # --- Salg: sist endrede ordrer ----------------------------------------
        try:
            with selv.env.cr.savepoint():
                if "sale.order" in selv.env:
                    rows = selv.env["sale.order"].search_read(
                        [],
                        ["name", "partner_id", "write_date"],
                        order="write_date desc",
                        limit=grense,
                    )
                    for r in rows:
                        rader.append(
                            {
                                "kilde": selv._kr_kilde_etikett("salg"),
                                "kode": r["name"] or "—",
                                "tekst": r["partner_id"][1] if r["partner_id"] else "—",
                                "naar": selv._kr_tid_tekst(naa, r["write_date"]),
                                "sort": r["write_date"] or False,
                                "model": "sale.order",
                                "res_id": r["id"],
                            }
                        )
        except Exception:
            _logger.warning("FIQ KR-lister: «siste aktivitet» — Salg feilet.", exc_info=True)

        # Nyest først. Rader uten dato havner sist i stedet for å krasje sorteringen.
        rader.sort(key=lambda r: r["sort"] or fields.Datetime.to_datetime("1970-01-01 00:00:00"), reverse=True)
        for r in rader:
            r.pop("sort", None)
        return {"totalt": len(rader), "rader": rader[:grense]}

    @api.model
    def get_kr_apne_oppgaver(self, company_id=False, sok=False, grense=12):
        """Seksjon 3 — «Åpne oppgaver — 6.02 SO». Rader med frist.

        Fasit (utkast 15, linje 844-851): etikett · nr · tekst · «frist 22.07.2026».
        Overskriften bærer det aktive søkefilteret — derfor returneres `filter` tilbake,
        så klienten viser DET som faktisk ble brukt og ikke det brukeren tror ble brukt.

        `sok` avgrenser på prosjektnavn/-nummer (fasitens «6.02 SO» er et prosjekt).
        🛑 Fritekst brukes ALDRI rått i SQL — den går inn som en ORM-domeneverdi, der
        Odoo parametriserer den selv.
        """
        selv = self.with_company(company_id) if company_id else self
        rader = []
        sok = (sok or "").strip()

        try:
            with selv.env.cr.savepoint():
                Task = selv.env["project.task"]
                # Åpen = ikke i en foldet (avsluttet) fase. `fold` er Odoos eget begrep
                # for «denne fasen er ferdig» — vi finner ikke opp en egen statusliste.
                domene = [("stage_id.fold", "=", False)]
                if sok:
                    domene += ["|", ("project_id.name", "ilike", sok), ("name", "ilike", sok)]
                felter = ["name", "date_deadline", "project_id"]
                if "code" in Task._fields:
                    felter.append("code")
                # Nærmeste frist først; oppgaver uten frist sist (Odoo sorterer NULL sist
                # på ASC i PostgreSQL).
                for r in Task.search_read(domene, felter, order="date_deadline asc, id asc", limit=grense):
                    frist = r.get("date_deadline")
                    if frist:
                        # 🛑 `date_deadline` er Datetime i Odoo 19 — konverter FØR bruk,
                        # ellers formaterer vi et klokkeslett som om det var en dato.
                        d = fields.Datetime.context_timestamp(selv, fields.Datetime.to_datetime(frist)).date()
                        naar = _("due %s") % d.strftime("%d.%m.%Y")
                    else:
                        naar = _("no due date")
                    rader.append(
                        {
                            "kilde": selv._kr_kilde_etikett("prj"),
                            "kode": r.get("code") or "—",
                            "tekst": r.get("name") or "—",
                            "naar": naar,
                            "model": "project.task",
                            "res_id": r["id"],
                        }
                    )
        except Exception:
            _logger.warning("FIQ KR-lister: «åpne oppgaver» feilet — seksjonen står tom.", exc_info=True)

        return {"totalt": len(rader), "filter": sok, "rader": rader}

    @api.model
    def get_kr_akt_perioder(self, company_id=False, grense=200):
        """Seksjon 4 — periode-bottene for grupperte aktiviteter (høyre kolonne).

        Fasit (utkast 15, linje 925-940): «Denne uken · Uke 23 · 2026 · Mai 2026 ·
        4. kvartal 2025 · Uten forfall», hver med et antall.

        🔑 GRUPPERINGEN OG FOLDINGEN FINNES ALLEREDE (`toggleAktGrp`, `isHead` i
        control_room.js — A-sporets fil). Denne metoden leverer BARE bottene med tall;
        den rører ikke fold-mekanikken.

        Bøtte-logikken er grovkornet med vilje, og blir grovere jo lenger tilbake du ser:
        denne uken → ukenummer (inneværende år) → måned → kvartal → år. Det speiler
        hvordan man faktisk leter: det nære er presist, det gamle er omtrentlig.
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        uke_start = i_dag - timedelta(days=i_dag.weekday())
        uke_slutt = uke_start + timedelta(days=6)

        # Rekkefølgen bevares: nyeste botte først, «Uten forfall» alltid sist.
        botter = []
        indeks = {}

        def _botte(nokkel, navn, rang):
            if nokkel not in indeks:
                indeks[nokkel] = {"key": nokkel, "navn": navn, "antall": 0, "rang": rang}
                botter.append(indeks[nokkel])
            indeks[nokkel]["antall"] += 1

        try:
            with selv.env.cr.savepoint():
                akt = selv.env["mail.activity"].search_read(
                    [("user_id", "=", selv.env.uid)], ["date_deadline"], limit=grense
                )
                for a in akt:
                    frist = a.get("date_deadline")
                    if not frist:
                        # Egen botte — «uten forfall» er en ekte tilstand, ikke en feil.
                        _botte("ingen", _("No due date"), -1)
                        continue
                    d = fields.Date.to_date(frist)
                    if uke_start <= d <= uke_slutt:
                        _botte("denne_uken", _("This week"), 100)
                    elif d.year == i_dag.year:
                        uke = d.isocalendar()[1]
                        _botte(f"uke-{d.year}-{uke}", _("Week %(week)s · %(year)s", week=uke, year=d.year), 90)
                    elif d.year == i_dag.year - 1 and d.month >= 10:
                        _botte(f"kv4-{d.year}", _("Q4 %(year)s", year=d.year), 50)
                    else:
                        _botte(
                            f"mnd-{d.year}-{d.month}",
                            _("%(month)s %(year)s", month=selv._kr_maaned_navn(d.month), year=d.year),
                            70,
                        )
        except Exception:
            _logger.warning("FIQ KR-lister: periode-bottene feilet — høyre kolonne viser ingen grupper.", exc_info=True)

        botter.sort(key=lambda b: b["rang"], reverse=True)
        for b in botter:
            b.pop("rang", None)
        return {"totalt": sum(b["antall"] for b in botter), "botter": botter}
