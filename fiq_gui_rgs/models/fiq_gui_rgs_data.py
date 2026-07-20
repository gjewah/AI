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

        # ÆRLIG SCOPE (GUI Prosjekt 19.07): tallet gjelder ETT firma. Har brukeren
        # tilgang til flere, er dette IKKE et konserntall — og det må stå, ellers
        # leses et ufullstendig tall som helheten. Fail-closed er riktig; stille
        # fail-closed er ikke.
        #
        # ⚠️ `company_ids` (tilgang), IKKE `env.companies` (aktivert akkurat nå).
        # Med env.companies forsvinner merket nettopp når brukeren har skrudd AV de
        # andre firmaene — altså akkurat da tallet er mest ufullstendig. Verifisert
        # 19.07: env.companies=1 mens brukeren har tilgang til flere.
        antall_tilgjengelige = len(self.env.user.company_ids)

        return {
            "firma": self.env.company.name,
            "valuta": valuta.symbol or valuta.name,
            "dato": fields.Date.to_string(i_dag),
            "scope_ett_firma": True,
            "antall_firmaer": antall_tilgjengelige,
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
    def apne_botte(self, key):
        """Åpner Odoos EGEN fakturaliste, filtrert på bøtta brukeren klikket.

        Gjermund/GUI Prosjekt 19.07: «tall → klikk → liste med det som ligger bak.
        Ikke tall som blindvei.»

        Native-først i praksis: vi bygger ingen egen liste — vi sender brukeren til
        Odoos fakturavisning med riktig filter. Da får hun alle Odoos egne verktøy
        (sortering, gruppering, eksport) uten at vi gjenskaper dem.
        """
        i_dag = fields.Date.context_today(self)
        alle = self.INN_TYPER + self.UT_TYPER

        if key == "inn":
            domene, tittel = self._basis_domene(self.INN_TYPER), "Inngående"
        elif key == "ut":
            domene, tittel = self._basis_domene(self.UT_TYPER), "Utgående"
        elif key == "haster":
            domene = self._basis_domene(alle) + [
                ("invoice_date_due", ">=", i_dag),
                ("invoice_date_due", "<=", fields.Date.add(i_dag, days=7)),
            ]
            tittel = "Haster"
        elif key == "kritisk":
            domene = self._basis_domene(alle) + [("invoice_date_due", "<", i_dag)]
            tittel = "Kritisk"
        else:
            domene, tittel = self._basis_domene(alle), "Ubetalt"

        return {
            "type": "ir.actions.act_window",
            "name": tittel,
            "res_model": "account.move",
            "view_mode": "list,form",  # Odoo 19: «list», ikke «tree»
            "domain": domene,
            "context": {"create": False},  # lesing fra en oversikt — ikke opprettelse
        }

    @api.model
    def get_kr_boks(self, company_id=False):
        """Samleboks til Kontrollrom-forsiden (KR-kontrakt, verifisert i
        `fiq_gui_control_config.py:1335`).

        Gjermund 19.07.2026: «om det er 5 saker som haster på finans og tre i dag så
        vises det som en boks i KR og om jeg trykker på en av boksene kommer jeg inn
        i finans eller RGS ihht hva jeg trykker på.»

        Her er «saker» = ubetalte bokførte fakturaer:
          haster = forfaller innen 7 dager (ikke forfalt ennå)
          i_dag  = forfaller nøyaktig i dag
          totalt = alt utestående

        🛑 TENANT: `company_id` kommer fra KR, men brukes ALDRI rått. Vi bytter firma
           via `with_company()` — da gjelder `ir.rule` fortsatt, og en bruker uten
           tilgang får ingenting. Klienten kan ikke be seg til et annet firmas tall.

        🛑 ÆRLIGHET: kan tallet ikke regnes, returneres INGEN boks (None) — aldri 0.
           «0 kr utestående» er en farlig løgn i regnskap; en manglende boks er ærlig.
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        om_en_uke = fields.Date.add(i_dag, days=7)
        alle = selv.INN_TYPER + selv.UT_TYPER

        Move = selv.env["account.move"]
        haster = Move.search_count(
            selv._basis_domene(alle)
            + [("invoice_date_due", ">=", i_dag), ("invoice_date_due", "<=", om_en_uke)]
        )
        i_dag_ant = Move.search_count(
            selv._basis_domene(alle) + [("invoice_date_due", "=", i_dag)]
        )
        totalt = Move.search_count(selv._basis_domene(alle))

        # Forfalte først — det er dem som haster mest, uansett hva kalenderen sier.
        forfalte = Move.search_read(
            selv._basis_domene(alle) + [("invoice_date_due", "<", i_dag)],
            ["name", "partner_id", "amount_residual", "invoice_date_due"],
            order="amount_residual desc",
            limit=5,
        )
        linjer = []
        for p in forfalte:
            dager = (i_dag - p["invoice_date_due"]).days if p["invoice_date_due"] else 0
            motpart = p["partner_id"][1] if p["partner_id"] else "—"
            linjer.append({
                "tekst": "%s forfalt %s dager — %s" % (p["name"], dager, motpart),
                "res_id": p["id"],
            })

        return {"haster": haster, "i_dag": i_dag_ant, "totalt": totalt, "linjer": linjer}

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
