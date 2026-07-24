from odoo import fields, models

# Rangering av nivåene (høyere tall = mer tilgang)
NIVAA_RANG = {"lese": 1, "skrive": 2, "administrere": 3}


class FiqTilgangRegel(models.Model):
    """Én arvbar tilgangsregel på et område (dokument-etikett). En regel defineres
    ÉN gang og arves nedover treet – den dupliseres ikke per underområde."""

    _name = "fiq.tilgang.regel"
    _description = "FIQ Tilgang – rettighetsregel (arvbar)"
    _rec_name = "ressurs_id"

    ressurs_id = fields.Many2one(
        "documents.tag",
        string="Område",
        required=True,
        index=True,
        ondelete="cascade",
        help="Området (dokument-etikett) regelen gjelder for. Arves nedover til underområder.",
    )
    subjekt_type = fields.Selection(
        [
            ("rolle", "Rolle"),
            ("gruppe", "Odoo-gruppe"),
            ("bruker", "Bruker"),
            ("partner", "Partner"),
        ],
        string="Gjelder for",
        default="rolle",
        required=True,
    )
    # `string=` utelatt på de tre under (pylint-odoo W8113): Odoo utleder samme
    # etikett fra feltnavnet — `rolle_id` → «Rolle». Feltnavnene er norske, så
    # etiketten forblir norsk uten parameteren.
    # 🛑 `gruppe_id` BEHOLDER sin: «Odoo-gruppe» er ULIKT feltnavnet, og ville
    #    blitt til «Gruppe» — som er upresist når det er en Odoo-rettighetsgruppe.
    rolle_id = fields.Many2one("fiq.tilgang.rolle")
    gruppe_id = fields.Many2one("res.groups", string="Odoo-gruppe")
    bruker_id = fields.Many2one("res.users")
    partner_id = fields.Many2one("res.partner")
    nivaa = fields.Selection(
        [("lese", "Lese"), ("skrive", "Skrive"), ("administrere", "Administrere")],
        string="Nivå",
        required=True,
        default="lese",
    )
    regel_type = fields.Selection(
        [("tildeling", "Tildeling"), ("brudd", "Brudd (stopp arv)")],
        string="Type",
        required=True,
        default="tildeling",
        help="Tildeling gir tilgang. Brudd stopper arv fra forelderen for dette området.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Selskap",
        default=lambda s: s.env.company,
    )

    def _gjelder_bruker(self, user):
        """Sant hvis regelen gjelder den gitte brukeren (via rolle/gruppe, bruker eller partner)."""
        self.ensure_one()
        if self.subjekt_type == "rolle":
            return bool(self.rolle_id) and self.rolle_id == user.fiq_tilgang_rolle_id
        if self.subjekt_type == "gruppe":
            # 🔴 ODOO 18-KODE RETTET 23.07.2026: her sto `user.groups_id`. Feltet heter
            # `group_ids` i Odoo 19 (odoo/addons/base/models/res_users.py) — målt i
            # `ir_model_fields`: res.users har `group_ids` og `all_group_ids`, IKKE
            # `groups_id`. Hver regel med subjekt_type = "gruppe" krasjet med
            # AttributeError. Vi bruker `all_group_ids` fordi den tar med ARVEDE
            # grupper (implied) — `group_ids` gir bare de direkte tildelte, og en
            # bruker som har gruppa via arv ville feilaktig fått nei.
            return bool(self.gruppe_id) and self.gruppe_id in user.all_group_ids
        if self.subjekt_type == "bruker":
            return self.bruker_id == user
        if self.subjekt_type == "partner":
            return bool(self.partner_id) and self.partner_id == user.partner_id
        return False
