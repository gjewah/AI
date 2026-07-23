# -*- coding: utf-8 -*-
from dateutil.relativedelta import relativedelta

from odoo import api, models

# 🔒 GDPR — RE-IDENTIFISERINGSGRENSE. Ikke en preferanse, en hard regel.
# En sum for ÉN ansatt er en personopplysning selv uten navn: én ansatt i en
# avdeling gjoer at beloepet identifiserer personen. Avtalt med 2.70 Finans og
# 2.80 RGS 22.07.2026 — se brain/kontrakt_lonn_2_20_til_rgs_2_80.md.
# 2.80 RGS har uttrykkelig bedt om aa bli holdt til denne grensen selv om et
# tall skulle vaere aldri saa nyttig.
MIN_ANSATTE = 3

# Arbeidsgiveravgift forfaller TERMINVIS: 6 terminer i aaret, den 15. i maaneden
# etter hver tomaanedersperiode. Termin 1 (jan-feb) forfaller 15. mars, osv.
AGA_TERMIN_MND = {1: 3, 2: 5, 3: 7, 4: 9, 5: 11, 6: 1}


class FiqLonnsforpliktelse(models.AbstractModel):
    """Loennsforpliktelser som aggregat til cashflow (2.80 RGS).

    Modellen bor HER, hos 2.20 Loenn. RGS og Finans KALLER — de eier aldri
    tallene, og de faar aldri underlaget.

    Kontrakten er laast mellom 2.20, 2.70 og 2.80. Endres formen, maa begge
    parter varsles: brain/kontrakt_lonn_2_20_til_rgs_2_80.md
    """

    _name = "fiq.lonnsforpliktelse"
    _description = "Lønnsforpliktelser — aggregater til cashflow"

    @api.model
    def hent_lonnsforpliktelser(self, fra_dato, til_dato, company_id=False):
        """Loennsforpliktelser med forfall i perioden.

        Returnerer en liste med dict-er paa den avtalte formen:
            type       lonn | aga | feriepenger | otp
            label      ferdig norsk tekst
            forfall    DATO pengene forlater konto (ikke perioden de gjelder)
            belop      positivt tall = utbetaling ut
            sikkerhet  bokfort | planlagt | estimat
            kilde      POG | Odoo — ren visning, aldri beregning
            periode    menneskelesbar fri tekst, ALDRI maskindato

        🔒 Ingen employee_id, ingen navn, ingen ansatt-referanse — heller ikke i
        `label`. Ingen linje som representerer faerre enn MIN_ANSATTE ansatte.

        ⚠️ `company_id` tas fra SESJONEN, aldri fra kalleren. En klient skal
        ikke kunne be seg til et annet firmas tall.
        """
        company = self.env.company
        forpliktelser = []
        forpliktelser += self._aga_forpliktelser(fra_dato, til_dato, company)
        return forpliktelser

    def _aga_forpliktelser(self, fra_dato, til_dato, company):
        """Arbeidsgiveravgift, gruppert per termin.

        ÉN LINJE PER FORFALL — ikke én sum per type. En kurve kan ikke plassere
        «AGA totalt 550 000»; den maa vite naar.
        """
        slipper = self.env["hr.payslip"].search([
            ("company_id", "=", company.id),
            ("state", "in", ("done", "paid", "verify")),
            ("date_to", ">=", fra_dato),
            ("date_to", "<=", til_dato),
        ])

        per_termin = {}
        for slip in slipper:
            termin = (slip.date_to.month - 1) // 2 + 1
            noekkel = (slip.date_to.year, termin)
            data = per_termin.setdefault(
                noekkel, {"belop": 0.0, "ansatte": set(), "bokfort": True}
            )
            try:
                data["belop"] += slip.fiq_aga_belop()
            except ValueError:
                # Sone mangler eller er ukjent. Linja utelates HELT heller enn aa
                # rapporteres med et gjettet tall — et hull som ser ut som en
                # null er farligere enn et synlig hull.
                continue
            data["ansatte"].add(slip.employee_id.id)
            if slip.state == "verify":
                data["bokfort"] = False

        linjer = []
        for (aar, termin), data in sorted(per_termin.items()):
            # 🔒 Re-identifiseringsgrensen. Linja utelates helt.
            if len(data["ansatte"]) < MIN_ANSATTE:
                continue
            if not data["belop"]:
                continue

            forfall_mnd = AGA_TERMIN_MND[termin]
            forfall_aar = aar + 1 if termin == 6 else aar
            forfall = self._forfallsdato(forfall_aar, forfall_mnd)

            linjer.append({
                "type": "aga",
                "label": "Arbeidsgiveravgift",
                "forfall": forfall,
                "belop": data["belop"],
                "sikkerhet": "bokfort" if data["bokfort"] else "planlagt",
                "kilde": "Odoo",
                "periode": "Termin %s %s" % (termin, aar),
            })
        return linjer

    def _forfallsdato(self, aar, mnd):
        """Den 15. i maaneden — AGA-terminens forfallsdag."""
        from datetime import date
        return date(aar, mnd, 15)
