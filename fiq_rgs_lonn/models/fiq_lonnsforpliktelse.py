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

    @api.model
    def status_forpliktelser(self, fra_dato, til_dato, company_id=False):
        """HVORFOR en forpliktelsestype mangler — ikke bare AT den mangler.

        Reist av 2.80 RGS 23.07: `mangler`-lista deres var binaer, mens
        virkeligheten har TRE tilstander:
            01  vi leverer linjer                       -> fjern fra `mangler`
            02  vi har ikke bygget typen ennaa          -> behold
            03  vi ER ferdige, men selskapet mangler
                data (f.eks. ingen sone registrert)     -> behold, MED GRUNN

        Uten denne metoden faar RGS samme svar — en tom liste — i tilstand 02 og
        03, og ville fjernet linja i den tro at typen var koblet. Da ser cashflow
        komplett ut mens en hel forpliktelsestype er borte.

        🔑 Grunnen kommer fra KILDEN. RGS skal ikke vedlikeholde sin egen
        oversettelse av vaare feilmodi — endrer vi oppfoersel, foelger teksten med.
        """
        company = self.env.company
        return {
            "aga": self._aga_status(fra_dato, til_dato, company),
            "lonn": {
                "levert": False,
                "grunn": "ikke_bygget",
                "forklaring": "Lønnskostnad er ikke tatt i bruk ennå",
            },
            "feriepenger": {
                "levert": False,
                "grunn": "ikke_bygget",
                "forklaring": "Feriepengeavsetning er ikke tatt i bruk ennå",
            },
            "otp": {
                "levert": False,
                "grunn": "ikke_bygget",
                "forklaring": "Tjenestepensjon er ikke tatt i bruk ennå",
            },
        }

    def _aga_status(self, fra_dato, til_dato, company):
        """Status for arbeidsgiveravgift — bygget, men avhenger av at sone finnes."""
        if not company.fiq_aga_sone:
            return {
                "levert": False,
                "grunn": "mangler_sone",
                "forklaring": (
                    "Selskapet har ingen sone for arbeidsgiveravgift registrert. "
                    "Sonen kan ikke utledes fra kommunen — etter regionreformen "
                    "er det ikke lenger én sone per kommune. Den må settes på "
                    "firmaet."
                ),
            }

        linjer = self._aga_forpliktelser(fra_dato, til_dato, company)
        if not linjer:
            return {
                "levert": False,
                "grunn": "ingen_data",
                "forklaring": (
                    "Ingen lønnsslipper i perioden, eller for få ansatte til at "
                    "tall kan vises uten å identifisere enkeltpersoner."
                ),
            }
        return {"levert": True, "grunn": None, "forklaring": None}

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
                noekkel,
                {"belop": 0.0, "ansatte": set(), "bokfort": True, "fribelop": set()},
            )
            try:
                data["belop"] += slip.fiq_aga_belop()
                status = slip.fiq_aga_fribelop_status()
                if status:
                    data["fribelop"].add(status)
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

            linje = {
                "type": "aga",
                "label": "Arbeidsgiveravgift",
                "forfall": forfall,
                "belop": data["belop"],
                "sikkerhet": "bokfort" if data["bokfort"] else "planlagt",
                "kilde": "Odoo",
                "periode": "Termin %s %s" % (termin, aar),
            }

            # VALGFRITT felt — forklarer hvorfor beloepet HOPPER i sone Ia/IVa.
            # 2.80 RGS spurte om `periode` var nok; det er den ikke. «Termin 3
            # 2026» sier ingenting om hvorfor terminen er dobbelt saa dyr som
            # forrige. Aa la flaten gjette ut fra beloepets stoerrelse ville
            # vaert nettopp den avledningen vi unngaar.
            # 🔒 Ren visning, aldri beregning — samme forpliktelse som `periode`.
            merknad = self._fribelop_merknad(data["fribelop"])
            if merknad:
                linje["merknad"] = merknad

            linjer.append(linje)
        return linjer

    def _fribelop_merknad(self, statuser):
        """Menneskelesbar forklaring paa fribeloeps-hoppet, eller None."""
        if "delvis" in statuser:
            return ("Fribeløpet ble brukt opp i denne terminen — "
                    "full sats for den overskytende delen")
        if "oppbrukt" in statuser:
            return "Fribeløpet er brukt opp — full sats fra og med denne terminen"
        return None

    def _forfallsdato(self, aar, mnd):
        """Den 15. i maaneden — AGA-terminens forfallsdag."""
        from datetime import date
        return date(aar, mnd, 15)
