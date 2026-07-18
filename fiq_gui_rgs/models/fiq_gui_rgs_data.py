# -*- coding: utf-8 -*-
"""Datakilde for AI GUI Regnskap (2.80) — likviditets-grunnbildet.

Rolle bak, flate foran: dette er VISNINGEN av «0.00 2.80 AI Regnskap-Rådgiver».
Native-først — tallene EIES av Odoo (`account.move`). Ingen parallell bokføring,
ingen egne summer lagret, ingen skriving. Kun lesing og gruppering.

🛑 «ALDRI gjett — regnskap er juridisk bindende» (rollens egen regel):
   alt her er BOKFØRTE tall (`state = posted`). Framskrivning/scenario hører
   hjemme et annet sted i flaten, tydelig merket — aldri blandet inn her.

🛑 TENANT-ISOLASJON: firma hentes fra `self.env.company` (sesjonen) — ALDRI som
   parameter fra klienten. Odoo håndhever `ir.rule` på toppen. En bruker kan
   dermed aldri be om et annet firmas tall ved å manipulere kallet.
"""

from odoo import api, fields, models
from odoo.fields import Command  # noqa: F401  (holdes for framtidig bruk)


class FiqGuiRgsData(models.AbstractModel):
    """Leser likviditetsbildet. AbstractModel = ingen tabell, ingen lagrede tall."""

    _name = "fiq.gui.rgs.data"
    _description = "FIQ Regnskap — likviditetsdata (lesing av account.move)"

    # Kundefakturaer = penger INN. Leverandørfakturaer = penger UT.
    # `out_refund`/`in_refund` (kreditnotaer) trekker automatisk ned via
    # amount_residual, som er negativ på dem — derfor tas de med i samme bøtte.
    INN_TYPER = ("out_invoice", "out_refund")
    UT_TYPER = ("in_invoice", "in_refund")

    @api.model
    def _basis_domene(self, typer):
        """Felles filter: bokført, ikke betalt, riktig firma.

        `state = posted` er det som gjør tallet til FAKTA. Kladd og kansellerte
        bilag er ikke bokført og skal aldri telle med i et likviditetsbilde.
        """
        return [
            ("move_type", "in", typer),
            ("state", "=", "posted"),
            ("payment_state", "not in", ("paid", "reversed")),
            ("company_id", "=", self.env.company.id),  # fra sesjonen, ikke fra klienten
        ]

    @api.model
    def _sum_restbelop(self, domene):
        """Summerer utestående beløp. `amount_residual` = det som faktisk gjenstår."""
        grupper = self.env["account.move"]._read_group(domene, aggregates=["amount_residual:sum"])
        return grupper[0][0] or 0.0 if grupper else 0.0

    @api.model
    def hent_grunnbilde(self):
        """Returnerer likviditets-grunnbildet for gjeldende firma.

        Bøttene er Gjermunds spesifikasjon: inn · ut · haster · kritisk · ubetalt.
        «Haster» og «kritisk» er tidsbaserte snitt av det UBETALTE — ikke egne
        pengestrømmer. De overlapper derfor bevisst med «ubetalt»; det er
        meningen (samme krone kan være både ubetalt og kritisk).
        """
        i_dag = fields.Date.context_today(self)
        om_en_uke = fields.Date.add(i_dag, days=7)

        inn = self._sum_restbelop(self._basis_domene(self.INN_TYPER))
        ut = self._sum_restbelop(self._basis_domene(self.UT_TYPER))

        # Haster = forfaller innen 7 dager, men er IKKE forfalt ennå.
        haster = self._sum_restbelop(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", ">=", i_dag), ("invoice_date_due", "<=", om_en_uke)]
        )
        # Kritisk = allerede forfalt. Dette er pengene som burde vært inne.
        kritisk = self._sum_restbelop(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", "<", i_dag)]
        )
        ubetalt = self._sum_restbelop(self._basis_domene(self.INN_TYPER + self.UT_TYPER))

        valuta = self.env.company.currency_id

        return {
            "firma": self.env.company.name,
            "valuta": valuta.symbol or valuta.name,
            "dato": fields.Date.to_string(i_dag),
            "botter": [
                {"key": "inn", "label": "Inngående", "verdi": inn,
                 "hjelp": "Bokførte kundefakturaer som ikke er betalt"},
                {"key": "ut", "label": "Utgående", "verdi": ut,
                 "hjelp": "Bokførte leverandørfakturaer som ikke er betalt"},
                {"key": "haster", "label": "Haster", "verdi": haster,
                 "hjelp": "Forfaller innen 7 dager"},
                {"key": "kritisk", "label": "Kritisk", "verdi": kritisk,
                 "hjelp": "Allerede forfalt"},
                {"key": "ubetalt", "label": "Ubetalt", "verdi": ubetalt,
                 "hjelp": "Alt utestående, inn og ut"},
            ],
            # Netto = det bildet daglig leder faktisk spør om: har vi penger igjen?
            "netto": inn - ut,
        }

    @api.model
    def hent_kritiske_poster(self, grense=10):
        """De største forfalte postene — så flaten kan vise HVILKE, ikke bare hvor mye.

        Navn, ikke ID-er (husets regel). Partner-navn er forretningsdata innenfor
        eget firma — tenant-grensa håndheves av domenet + `ir.rule`.
        """
        poster = self.env["account.move"].search_read(
            self._basis_domene(self.INN_TYPER + self.UT_TYPER)
            + [("invoice_date_due", "<", fields.Date.context_today(self))],
            ["name", "partner_id", "amount_residual", "invoice_date_due", "move_type"],
            order="amount_residual desc",
            limit=grense,
        )
        return [
            {
                "nummer": p["name"],
                "motpart": p["partner_id"][1] if p["partner_id"] else "—",
                "belop": p["amount_residual"],
                "forfall": p["invoice_date_due"],
                "retning": "inn" if p["move_type"] in self.INN_TYPER else "ut",
            }
            for p in poster
        ]
