"""Stabil SharePoint-referanse på dokumentet.

Prinsipp (Gjermund 2026-07-05): SharePoint eier filene — Odoo eier metadata + lenker.
Feltene her bærer den FASTE referansen, som overlever omdøping og flytting.
"""

from odoo import _, fields, models
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    sp_drive_id = fields.Char(
        string="SP bibliotek-ID",
        index=True,
        copy=False,
        help="SharePoint drive-ID (dokumentbiblioteket). Sammen med SP fil-ID "
        "identifiserer den dokumentet entydig — item-ID alene er ikke unik "
        "på tvers av biblioteker.",
    )
    sp_item_id = fields.Char(
        string="SP fil-ID",
        index=True,
        copy=False,
        help="SharePoint driveItem-ID. Overlever omdøping og flytting; URL-en kan "
        "regenereres fra den. Dette er den stabile nøkkelen mot SharePoint.",
    )
    sp_web_url = fields.Char(
        string="SP-lenke",
        copy=False,
        help="Nettadressen slik den var ved siste synk. Kun til visning — ved tvil "
        "er det ID-ene som gjelder, ikke denne.",
    )
    sp_sist_synk = fields.Datetime(
        string="SP sist synkronisert",
        copy=False,
        readonly=True,
        help="Når ID-ene sist ble hentet fra SharePoint.",
    )
    sp_har_referanse = fields.Boolean(
        string="Har SP-referanse",
        compute="_compute_sp_har_referanse",
        store=True,
        help="Sant når både bibliotek-ID og fil-ID er satt — da kan dokumentet "
        "finnes igjen i SharePoint uansett om det er flyttet eller omdøpt.",
    )

    _sql_constraints = [
        (
            "sp_item_unik_per_drive",
            "unique(sp_drive_id, sp_item_id)",
            "Samme SharePoint-fil kan bare være registrert én gang.",
        ),
    ]

    @property
    def _sp_referanse_felt(self):
        return ("sp_drive_id", "sp_item_id")

    def _compute_sp_har_referanse(self):
        for doc in self:
            doc.sp_har_referanse = bool(doc.sp_drive_id and doc.sp_item_id)

    # ------------------------------------------------------------------
    # Skriving — brukes av høstingen (utenfor Odoo) og senere av broen
    # ------------------------------------------------------------------
    def sett_sp_referanse(self, drive_id, item_id, web_url=None):
        """Setter den stabile SharePoint-referansen på dokumentet.

        Egen metode framfor rå write() slik at høstingen har ett inngangspunkt
        som kan utvides (logging, validering) uten at kallerne endres.
        """
        self.ensure_one()
        if not drive_id or not item_id:
            raise UserError(
                _(
                    "Både bibliotek-ID og fil-ID må oppgis — item-ID alene er ikke entydig."
                )
            )
        vals = {
            "sp_drive_id": drive_id,
            "sp_item_id": item_id,
            "sp_sist_synk": fields.Datetime.now(),
        }
        if web_url:
            vals["sp_web_url"] = web_url
        self.write(vals)
        return True

    def finn_pa_sp_referanse(self, drive_id, item_id):
        """Slår opp et dokument på den stabile referansen. Tom recordset om ingen match."""
        if not (drive_id and item_id):
            return self.browse()
        return self.search(
            [("sp_drive_id", "=", drive_id), ("sp_item_id", "=", item_id)], limit=1
        )
