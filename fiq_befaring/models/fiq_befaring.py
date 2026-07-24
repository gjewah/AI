#
# Befarings-økt (befaring_module_spec, Gjermund 2026-06-21).
# Starter i SALGSPROSESSEN: knyttes til en salgsmulighet (crm.lead), fanger rom + funn,
# genererer romskjema, fyller tilbud (sale.order) og overføres til prosjektet (project.project)
# under oppgaven «Befaring». GENERISK kjerne for alle FIQ-kunder — bransjelag legges oppå.
# Tenant-isolert: company_id (default aktivt firma) + global multi-company record rule.

from odoo import _, api, fields, models


class FiqBefaring(models.Model):
    _name = "fiq.befaring"
    _description = "Befaring (salgsmulighet → romskjema → tilbud → prosjekt)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "dato desc, id desc"

    name = fields.Char(
        string="Befaring",
        required=True,
        index=True,
        copy=False,
        default=lambda self: _("Ny befaring"),
        tracking=True,
        help="Navn på befaringen — navn, ikke ID.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Firma",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        help="Firmaet (tenant) befaringen tilhører. Styrer tenant-isolasjon.",
    )
    lead_id = fields.Many2one(
        "crm.lead",
        string="Salgsmulighet",
        index=True,
        tracking=True,
        help="Salgsmuligheten befaringen starter fra (befaring i salgsprosessen).",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Kunde",
        index=True,
        tracking=True,
        help="Kunden befaringen gjelder — arves fra salgsmuligheten.",
    )
    sale_order_id = fields.Many2one(
        "sale.order",
        string="Tilbud",
        index=True,
        tracking=True,
        help="Tilbudet (sale.order) befaringen fyller / er koblet til.",
    )
    project_id = fields.Many2one(
        "project.project",
        string="Prosjekt",
        index=True,
        tracking=True,
        help="Prosjektet befaringen overføres til ved aksept.",
    )
    befaring_task_id = fields.Many2one(
        "project.task",
        string="Oppgave «Befaring»",
        help="Oppgaven på prosjektet der befarings-dokumentene samles.",
    )
    dato = fields.Date(
        string="Befaringsdato", default=fields.Date.context_today, tracking=True
    )
    utfort_av_id = fields.Many2one(
        "res.users",
        string="Befarer",
        default=lambda self: self.env.user,
        tracking=True,
        help="Den som utfører befaringen.",
    )
    state = fields.Selection(
        [
            ("utkast", "Utkast"),
            ("pagaar", "Pågår"),
            ("fullfort", "Fullført"),
            ("overfort", "Overført til prosjekt"),
        ],
        string="Status",
        default="utkast",
        required=True,
        index=True,
        tracking=True,
    )
    notat = fields.Text(string="Generelt notat")

    rom_ids = fields.One2many("fiq.befaring.rom", "befaring_id")
    funn_ids = fields.One2many(
        "fiq.befaring.funn", "befaring_id", string="Funn / avvik"
    )

    rom_antall = fields.Integer(
        string="Antall rom", compute="_compute_antall", store=True
    )
    funn_antall = fields.Integer(
        string="Antall funn", compute="_compute_antall", store=True
    )

    @api.depends("rom_ids", "funn_ids")
    def _compute_antall(self):
        for b in self:
            b.rom_antall = len(b.rom_ids)
            b.funn_antall = len(b.funn_ids)

    @api.onchange("lead_id")
    def _onchange_lead_id(self):
        """Arv kunde fra salgsmuligheten (navn, ikke ID)."""
        for b in self:
            if b.lead_id and b.lead_id.partner_id:
                b.partner_id = b.lead_id.partner_id

    # ------------------------------------------------------------------ API
    @api.model
    def opprett_fra_lead(self, lead_id, name=None):
        """Start en befaring fra en salgsmulighet. Returnerer den nye befaringens id.
        Arver kunde + firma fra salgsmuligheten (tenant-isolasjon respekteres)."""
        lead = self.env["crm.lead"].browse(lead_id)
        if not lead.exists():
            return False
        vals = {
            "name": name or (_("Befaring — %s") % (lead.name or lead.display_name)),
            "lead_id": lead.id,
            "partner_id": lead.partner_id.id or False,
            "company_id": lead.company_id.id or self.env.company.id,
            "state": "pagaar",
        }
        return self.create(vals).id

    def get_romskjema_data(self):
        """Strukturert romskjema-data fra rom-linjene (grunnlag for QWeb/Excel-eksport
        i bransjelaget). Rene data — ingen skriv."""
        self.ensure_one()
        return {
            "befaring": self.name,
            "kunde": self.partner_id.display_name or "",
            "dato": self.dato and fields.Date.to_string(self.dato) or "",
            "rom": [
                {
                    "rom": r.name,
                    "etasje": r.etasje or "",
                    "areal": r.areal,
                    "tiltak": r.tiltak or "",
                    "ai_tiltak_no": r.ai_tiltak_no or "",
                    "ai_tiltak_en": r.ai_tiltak_en or "",
                    "funn": [
                        {
                            "navn": f.name,
                            "type": f.type,
                            "alvorlighet": f.alvorlighet,
                            "status": f.status,
                        }
                        for f in r.funn_ids
                    ],
                }
                for r in self.rom_ids.sorted(key=lambda x: (x.sequence, x.id))
            ],
        }

    def populer_kalkulator_data(self):
        """Mapper rom/tiltak → kandidat-tilbudslinjer (Post→detalj). Returnerer rene data;
        selve skrivingen til sale.order.line gjøres av bransje-/kalkulator-overlaget
        (holdes generisk og skrivfri her)."""
        self.ensure_one()
        linjer = []
        for r in self.rom_ids.sorted(key=lambda x: (x.sequence, x.id)):
            tekst = r.ai_tiltak_no or r.tiltak or ""
            if not tekst:
                continue
            etikett = r.name if not r.etasje else f"{r.name} ({r.etasje})"
            linjer.append(
                {
                    "rom_id": r.id,
                    "post": etikett,
                    "beskrivelse": tekst,
                    "areal": r.areal,
                }
            )
        return linjer

    def overfor_til_prosjekt(self):
        """Ved aksept: finn/opprett oppgaven «Befaring» på prosjektet og koble befaringen dit.
        Dokument-overføring lead→oppgave gjøres av crm_sale_project.move_attachments-hooken
        (kobles i bransjelaget); her sikres selve oppgave-ankeret + status. Menneske styrer
        når dette kjøres (knapp)."""
        self.ensure_one()
        if not self.project_id:
            return False
        Task = self.env["project.task"]
        task = self.befaring_task_id
        if not task or task.project_id != self.project_id:
            task = Task.search(
                [
                    ("project_id", "=", self.project_id.id),
                    ("name", "=", _("Befaring")),
                ],
                limit=1,
            )
        if not task:
            task = Task.create(
                {
                    "name": _("Befaring"),
                    "project_id": self.project_id.id,
                    "company_id": self.company_id.id,
                }
            )
        self.befaring_task_id = task.id
        self.state = "overfort"
        return task.id

    # ------------------------------------------------------------- UI-knapper
    def action_start(self):
        for b in self:
            if b.state == "utkast":
                b.state = "pagaar"

    def action_fullfor(self):
        for b in self:
            b.state = "fullfort"

    def action_overfor(self):
        self.overfor_til_prosjekt()
