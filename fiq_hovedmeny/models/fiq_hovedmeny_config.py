# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api

WIDGETS = ["kpis", "projects", "kommunikasjon", "activity", "tasks", "chart", "copilot", "quick"]


class FiqHovedmenyConfig(models.Model):
    """Per-bruker/per-firma oppsett for Hovedmeny (FIQs egenutviklede styringslag
    oppå res.groups): nivå + hvilke widgets som vises. Governert av rettighetsgrupper
    + record rules (bruker ser kun sitt eget)."""
    _name = "fiq.hovedmeny.config"
    _description = "FIQ Hovedmeny – brukeroppsett"
    _rec_name = "user_id"

    user_id = fields.Many2one(
        "res.users", string="Bruker", required=True, index=True, ondelete="cascade",
        default=lambda s: s.env.user,
    )
    company_id = fields.Many2one(
        "res.company", string="Firma", required=True, index=True,
        default=lambda s: s.env.company,
    )
    level = fields.Selection(
        [("pulse", "Pulse (sammendrag)"), ("balansert", "Balansert"), ("detaljert", "Detaljert")],
        string="Detaljnivå", default="balansert", required=True,
        help="Rollebasert detaljnivå: Pulse (daglig leder) · Balansert (prosjektleder) · Detaljert (power).",
    )
    show_kpis = fields.Boolean("KPI-rad", default=True)
    show_projects = fields.Boolean("Prosjektoversikt", default=True)
    show_kommunikasjon = fields.Boolean("Kommunikasjon", default=True)
    show_activity = fields.Boolean("Aktivitet", default=True)
    show_tasks = fields.Boolean("Oppgaver", default=True)
    show_chart = fields.Boolean("Fremdriftsdiagram", default=True)
    show_copilot = fields.Boolean("AI Copilot", default=True)
    show_quick = fields.Boolean("Hurtigvalg", default=True)

    # Odoo 19: bruk models.Constraint (ikke deprecated _sql_constraints)
    _user_company_uniq = models.Constraint(
        "unique(user_id, company_id)",
        "Ett Hovedmeny-oppsett per bruker per firma.",
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
        logo = comp.fiq_hovedmeny_logo
        if logo:
            logo = logo.decode() if isinstance(logo, bytes) else logo
        return {
            "id": rec.id,
            "level": rec.level,
            "show": {w: bool(rec["show_" + w]) for w in WIDGETS},
            "is_admin": self.env.user.has_group("fiq_hovedmeny.group_admin"),
            # Firma/branding hentes server-side (ingen avhengighet av company-service i OWL)
            "company_name": comp.name or "",
            "accent": comp.fiq_hovedmeny_accent or "#38B44A",
            "logo": ("data:image/png;base64,%s" % logo) if logo else False,
        }

    @api.model
    def set_widget(self, widget, value):
        if widget in WIDGETS:
            self._get_or_create_current().write({"show_" + widget: bool(value)})
        return True

    @api.model
    def get_kommunikasjon(self, period="uke", limit=40):
        """«Kommunikasjon»-flate (GENERISK – alle modeller/elementer, ikke SDV-spesifikk):
        siste kommunikasjon (e-post/meldinger) PÅ elementer brukeren har tilgang til, med lenke.
        period = dag|uke|maaned|alle. Kjøres som brukeren → record rules styrer synlighet."""
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
            # Retning «sendt fra»: meldinger skrevet av en intern bruker = SENDT (utgående/
            # logget av oss); alt annet (ekstern avsender, ren innkommende e-post) = MOTTATT.
            # Gjør det enkelt for AI/bruker å skille hva som kom inn vs. hva vi sendte.
            internal = bool(
                m.author_id
                and m.author_id.user_ids
                and any(not u.share for u in m.author_id.user_ids)
            )
            out.append({
                "id": m.id,
                "kind": "E-post" if m.message_type == "email" else "Melding",
                "author": author,
                "author_id": m.author_id.id if m.author_id else False,
                "direction": "sendt" if internal else "mottatt",
                "subject": subject[:90] or "(uten emne)",
                "date": m.date.strftime("%d.%m %H:%M") if m.date else "",
                "model": m.model,
                "res_id": m.res_id,
                "element": element,
            })
        return out

    @api.model
    def action_reply(self, message_id, reply_all=False):
        """Svar / Svar alle på en kommunikasjon → åpne e-post-komponist pre-fylt.
        CC/BCC tilgjengelig via mail_composer_cc_bcc. (FIQ-compose kanoniseres senere.)"""
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
            "name": "Svar alle" if reply_all else "Svar",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": ctx,
        }

    # Kandidat-dashbord (Odoos native analyser/dashboards). Vises KUN hvis xmlid finnes
    # i kundens DB → trygt på tvers av tenanter (env.ref-guard, ingen harde avhengigheter).
    _DASHBOARD_CANDIDATES = [
        ("spreadsheet_dashboard.ir_actions_dashboard_action", "Dashboards (Odoo)"),
        ("sale.action_order_report_all", "Salgsanalyse"),
        ("account.action_account_invoice_report_all", "Fakturaanalyse"),
        ("purchase.action_purchase_order_report_all", "Innkjøpsanalyse"),
        ("crm.crm_opportunity_report_action", "Pipeline-analyse"),
        ("hr_timesheet.timesheet_action_report_by_project", "Timeanalyse"),
    ]

    @api.model
    def get_dashboards(self):
        """Returnerer de native dashboard-/analyse-handlingene som faktisk finnes i denne
        DB-en (xmlid resolver). Front-end åpner dem in-page via doAction(xmlid) – SSOT,
        ingen duplisering av Odoos egne dashboards."""
        out = []
        for xmlid, label in self._DASHBOARD_CANDIDATES:
            if self.env.ref(xmlid, raise_if_not_found=False):
                out.append({"xmlid": xmlid, "label": label})
        return out

    @api.model
    def _action_set_home_all(self):
        """Admin-styrt: sett Hovedmeny som oppstart KUN for firma der
        `fiq_hovedmeny_as_home` er PÅ; ellers lås opp (nullstill vår home-action).
        Kalles via <function> ved install OG oppgradering. Aldri tvungen på alle."""
        action = self.env.ref("fiq_hovedmeny.action_fiq_hovedmeny", raise_if_not_found=False)
        if not action:
            return True
        Users = self.env["res.users"]
        for comp in self.env["res.company"].search([]):
            users = Users.search([("share", "=", False), ("company_id", "=", comp.id)])
            if comp.fiq_hovedmeny_as_home:
                users.write({"action_id": action.id})
            else:
                # Lås opp: nullstill kun de som faktisk peker på Hovedmeny
                locked = users.filtered(lambda u: u.action_id and u.action_id.id == action.id)
                if locked:
                    locked.write({"action_id": False})
        return True
