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
        }

    @api.model
    def set_widget(self, widget, value):
        if widget in WIDGETS:
            self._get_or_create_current().write({"show_" + widget: bool(value)})
        return True

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
