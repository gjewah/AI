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

# `periode` skal vaere MENNESKELESBAR, aldri en maskindato (kontrakt-krav fra
# 2.80 RGS). «August 2026» — ikke «2026-08».
MAANEDER = {
    1: "Januar", 2: "Februar", 3: "Mars", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November",
    12: "Desember",
}


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
        forpliktelser += self._lonn_forpliktelser(fra_dato, til_dato, company)
        forpliktelser += self._aga_forpliktelser(fra_dato, til_dato, company)
        forpliktelser += self._feriepenger_forpliktelser(fra_dato, til_dato, company)
        forpliktelser += self._otp_forpliktelser(fra_dato, til_dato, company)
        return forpliktelser

    def _otp_forpliktelser(self, fra_dato, til_dato, company):
        """Pensjonsinnskudd — betales normalt KVARTALSVIS til leverandoeren.

        📌 Terminen foelger AVTALEN med pensjonsleverandoeren, ikke loven.
        Kvartalsvis er vanligst; noen betaler maanedlig. Vi bruker kvartal som
        standard og merker linjene `estimat` — de er ikke bokfoerte krav slik
        AGA-terminene er.
        """
        slipper = self.env["hr.payslip"].search([
            ("company_id", "=", company.id),
            ("state", "in", ("validated", "paid")),
            ("date_to", ">=", fra_dato),
            ("date_to", "<=", til_dato),
        ])

        per_kvartal = {}
        for slip in slipper:
            innskudd = slip.fiq_otp_innskudd()
            if not innskudd:
                # Ansatte under aldersgrensen gir 0 — de skal heller ikke
                # telle med i ansatt-antallet for personverngrensen.
                continue
            kvartal = (slip.date_to.month - 1) // 3 + 1
            data = per_kvartal.setdefault(
                (slip.date_to.year, kvartal), {"belop": 0.0, "ansatte": set()},
            )
            data["belop"] += innskudd
            data["ansatte"].add(slip.employee_id.id)

        from datetime import date
        linjer = []
        for (aar, kvartal), data in sorted(per_kvartal.items()):
            if len(data["ansatte"]) < MIN_ANSATTE or not data["belop"]:
                continue
            # Forfall: den 15. i maaneden ETTER kvartalets slutt.
            forfall_mnd = kvartal * 3 + 1
            forfall_aar = aar
            if forfall_mnd > 12:
                forfall_mnd, forfall_aar = 1, aar + 1

            linjer.append({
                "type": "otp",
                "label": "Tjenestepensjon",
                "forfall": date(forfall_aar, forfall_mnd, 15),
                "belop": data["belop"],
                "sikkerhet": "estimat",
                "kilde": "Odoo",
                "periode": "Q%s %s" % (kvartal, aar),
            })
        return linjer

    def _feriepenger_forpliktelser(self, fra_dato, til_dato, company):
        """Feriepenger — opptjent ETT aar, utbetalt DET NESTE.

        🔑 Dette er den stoerste periodeforskyvningen i hele kontrakten:
        feriepenger opptjent gjennom hele 2025 forlater konto i JUNI 2026.
        `periode` sier «Opptjent 2025», `forfall` sier 2026-06-15 — og begge
        er sanne. Det er nettopp derfor 2.80 RGS ba om `periode`-feltet.

        🔒 Satsen avhenger av ALDER (ferieloven § 10), men aggregatet leverer
        KUN summen. Fordelingen mellom satsene forlater aldri HR — den ville
        roepet hvem som er over 60.
        """
        slipper = self.env["hr.payslip"].search([
            ("company_id", "=", company.id),
            ("state", "in", ("validated", "paid")),
            ("date_to", ">=", fra_dato),
            ("date_to", "<=", til_dato),
        ])

        per_aar = {}
        for slip in slipper:
            aar = slip.date_to.year
            data = per_aar.setdefault(
                aar, {"belop": 0.0, "ansatte": set(), "bokfort": True}
            )
            data["belop"] += slip.fiq_feriepenger_avsetning(opptjeningsaar=aar)
            data["ansatte"].add(slip.employee_id.id)
            if slip.state != "paid":
                data["bokfort"] = False

        from datetime import date
        linjer = []
        for aar, data in sorted(per_aar.items()):
            if len(data["ansatte"]) < MIN_ANSATTE or not data["belop"]:
                continue
            linjer.append({
                "type": "feriepenger",
                "label": "Feriepenger",
                # Utbetales normalt i juni AARET ETTER opptjening
                # (ferieloven § 11: siste vanlige loenningsdag foer ferien).
                "forfall": date(aar + 1, 6, 15),
                "belop": data["belop"],
                # Avsetningen er alltid et ESTIMAT foer ferieaaret: grunnlaget
                # vokser med hver loennskjoering ut opptjeningsaaret.
                "sikkerhet": "estimat",
                "kilde": "Odoo",
                "periode": "Opptjent %s" % aar,
            })
        return linjer

    def _lonn_forpliktelser(self, fra_dato, til_dato, company):
        """Loennskostnad — det som faktisk forlater konto til de ansatte.

        🔑 NETTOLOENN, ikke brutto. Cashflow spoer hva som forlater konto:
        forskuddstrekket gaar til Skatteetaten som en EGEN betaling med egen
        termin, ikke til den ansatte. Brukte vi brutto, ville vi telt
        skattetrekket to ganger naar trekket senere legges inn som egen type.

        ÉN LINJE PER FORFALL — loenn utbetales den 15., og hver maaned er en
        egen utbetaling. En sum for hele aaret kan ikke plasseres i en kurve.
        """
        slipper = self.env["hr.payslip"].search([
            ("company_id", "=", company.id),
            ("state", "in", ("validated", "paid")),
            ("date_to", ">=", fra_dato),
            ("date_to", "<=", til_dato),
        ])

        per_maaned = {}
        for slip in slipper:
            noekkel = (slip.date_to.year, slip.date_to.month)
            data = per_maaned.setdefault(
                noekkel, {"belop": 0.0, "ansatte": set(), "bokfort": True}
            )
            data["belop"] += slip.net_wage
            data["ansatte"].add(slip.employee_id.id)
            if slip.state != "paid":
                data["bokfort"] = False

        linjer = []
        for (aar, mnd), data in sorted(per_maaned.items()):
            # 🔒 Re-identifiseringsgrensen — samme regel som for AGA.
            if len(data["ansatte"]) < MIN_ANSATTE or not data["belop"]:
                continue

            linjer.append({
                "type": "lonn",
                "label": "Lønnskjøring",
                "forfall": self._lonn_forfall(aar, mnd),
                "belop": data["belop"],
                "sikkerhet": "bokfort" if data["bokfort"] else "planlagt",
                "kilde": "Odoo",
                "periode": "%s %s" % (MAANEDER[mnd], aar),
            })
        return linjer

    def _lonn_forfall(self, aar, mnd):
        """Loenn utbetales den 15. i MAANEDEN ETTER opptjeningsmaaneden.

        Derfor spriker `periode` og `forfall` systematisk: augustloenn staar
        som «August 2026» men forfaller 15. september. Det er nettopp den
        forskjellen 2.80 RGS ba om `periode`-feltet for — riktig for
        likviditeten, forklarlig for leseren.
        """
        from datetime import date
        return date(aar + 1, 1, 15) if mnd == 12 else date(aar, mnd + 1, 15)

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
            "lonn": self._lonn_status(fra_dato, til_dato, company),
            "feriepenger": self._feriepenger_status(fra_dato, til_dato, company),
            "otp": self._otp_status(fra_dato, til_dato, company),
        }

    def _lonn_status(self, fra_dato, til_dato, company):
        """Status for loennskostnad. Trenger IKKE sone — nettoloenn er
        uavhengig av arbeidsgiveravgift."""
        if self._lonn_forpliktelser(fra_dato, til_dato, company):
            return {"levert": True, "grunn": None, "forklaring": None}
        return {
            "levert": False,
            "grunn": "ingen_data",
            "forklaring": (
                "Ingen lønnskjøringer i perioden, eller for få ansatte til at "
                "tall kan vises uten å identifisere enkeltpersoner."
            ),
        }

    def _otp_status(self, fra_dato, til_dato, company):
        """Status for tjenestepensjon."""
        if self._otp_forpliktelser(fra_dato, til_dato, company):
            return {"levert": True, "grunn": None, "forklaring": None}
        return {
            "levert": False,
            "grunn": "ingen_data",
            "forklaring": (
                "Ingen lønnskjøringer å beregne pensjonsinnskudd av i "
                "perioden, eller for få ansatte til at tall kan vises uten å "
                "identifisere enkeltpersoner."
            ),
        }

    def _feriepenger_status(self, fra_dato, til_dato, company):
        """Status for feriepengeavsetning."""
        if self._feriepenger_forpliktelser(fra_dato, til_dato, company):
            return {"levert": True, "grunn": None, "forklaring": None}
        return {
            "levert": False,
            "grunn": "ingen_data",
            "forklaring": (
                "Ingen lønnskjøringer å beregne feriepenger av i perioden, "
                "eller for få ansatte til at tall kan vises uten å "
                "identifisere enkeltpersoner."
            ),
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
            # Odoo 19-tilstander: draft | validated | paid | cancel.
            # 🔴 IKKE 'done'/'verify' — de er Odoo 18-navn. Verifisert i
            # hr_payroll/models/hr_payslip.py. Med de gamle navnene ville
            # VALIDERTE loennskjoeringer aldri naadd cashflow.
            ("state", "in", ("validated", "paid")),
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
            # `paid` = pengene er utbetalt -> bokfoert faktum.
            # `validated` = bekreftet, men ikke utbetalt -> planlagt.
            # 🔑 Vi laaser SAMMENHENGEN, ikke en tilstandsverdi: er slippen
            # utbetalt, er tallet bokfoert; er den ikke det, er det planlagt.
            # (2.80 RGS 23.07: tester som laaser ÉN tilstand laaser ETT miljoe.)
            if slip.state != "paid":
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
