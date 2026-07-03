# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api, _

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
        }

    @api.model
    def set_widget(self, widget, value):
        if widget in WIDGETS:
            self._get_or_create_current().write({"show_" + widget: bool(value)})
        return True

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
    def get_presence(self):
        """«Til stede nå»: interne brukere (share=False, active=True) med
        tilgjengelighets-status fra res.users.im_status.
        Defensiv: hvis im_status-feltet mangler (ingen bus/presence-modul) → 'offline'.
        status → 'online' (grønn) | 'away' (gul) | 'offline' (grå)."""
        Users = self.env["res.users"]
        # NB: login_date er et ikke-lagret relatert felt (related=log_ids.create_date)
        # og kan IKKE brukes i SQL ORDER BY i Odoo 19 → sorter på lagret felt (navn).
        users = Users.search(
            [("share", "=", False), ("active", "=", True)],
            order="name", limit=24,
        )
        out = []
        for u in users:
            # im_status er et computed felt (krever bus). Les defensivt.
            try:
                raw = u.im_status or "offline"
            except Exception:
                raw = "offline"
            # Normaliser: Odoo gir online|away|offline (+ *_ios varianter)
            if raw.startswith("online"):
                status = "online"
            elif raw.startswith("away"):
                status = "away"
            else:
                status = "offline"
            name = u.name or u.login or "—"
            # Initialer (maks 2) fra navnet
            parts = [p for p in name.replace("-", " ").split(" ") if p]
            if len(parts) >= 2:
                initialer = (parts[0][:1] + parts[-1][:1]).upper()
            elif parts:
                initialer = parts[0][:2].upper()
            else:
                initialer = "?"
            # Har brukeren et ansattbilde? (kun flagg – vi laster ikke selve bildet her)
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
                "status": status,
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
