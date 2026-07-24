from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq")
class TestAgaSatser(TransactionCase):
    """Satsene er juridisk bindende. Testene sjekker at TALLENE stemmer med
    Stortingsvedtak FOR-2025-12-18-2748 § 3 — ikke bare at koden kjoerer."""

    def _sats(self, kode):
        # _get_parameter_from_code kalles paa MODELLEN, ikke paa en post
        # (verifisert i hr_payroll/models/hr_rule_parameter.py:75).
        # Datoen avgjoer hvilken versjon av satsen som gjelder.
        from datetime import date

        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            kode,
            date(2026, 6, 1),
        )

    def test_01_alle_syv_soner_finnes(self):
        satser = self._sats("no_aga_sonesatser")
        self.assertEqual(
            sorted(satser),
            ["1", "1a", "2", "3", "4", "4a", "5"],
            "Norge har sju AGA-soner. Mangler en, blir loennskjoeringen feil "
            "for alle i den sonen.",
        )

    def test_02_satsene_stemmer_med_stortingsvedtaket(self):
        # Kilde: FOR-2025-12-18-2748 § 3 foerste ledd, bekreftet mot
        # skatteetaten.no/satser/arbeidsgiveravgift.
        fasit = {
            "1": 14.1,
            "1a": 10.6,
            "2": 10.6,
            "3": 6.4,
            "4": 5.1,
            "4a": 7.9,
            "5": 0.0,
        }
        self.assertEqual(self._sats("no_aga_sonesatser"), fasit)

    def test_03_fribelop_2026(self):
        # § 4 fjerde ledd.
        self.assertEqual(self._sats("no_aga_fribelop"), 850000)

    def test_04_full_sats_er_sone_1(self):
        # Full sats brukes som REFERANSE i fribeloepsberegningen. Spriker den
        # fra sone I, er en av dem feil.
        self.assertEqual(
            self._sats("no_aga_full_sats"),
            self._sats("no_aga_sonesatser")["1"],
        )


@tagged("post_install", "-at_install", "fiq")
class TestAgaSone(TransactionCase):
    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Testfirma AGA",
                "fiq_aga_sone": "2",
            }
        )

    def test_05_selskapets_sone_er_hovedregelen(self):
        slip = self.env["hr.payslip"].new({"company_id": self.company.id})
        self.assertEqual(slip.fiq_aga_sone(), "2")

    def test_06_manglende_sone_stopper_kjoringen(self):
        """En manglende sone skal STOPPE, ikke gi 0 % eller en gjettet sats.
        En stille null her blir en avviksmelding fra Skatteetaten."""
        tom = self.env["res.company"].create({"name": "Uten sone"})
        slip = self.env["hr.payslip"].new({"company_id": tom.id})
        with self.assertRaises(ValueError):
            slip.fiq_aga_sats()


@tagged("post_install", "-at_install", "fiq")
class TestAgaFribelop(TransactionCase):
    """Sone Ia er IKKE en ren sats — redusert sats gjelder bare til fribeloepet
    er brukt opp. Det er den vanskeligste delen av regelverket."""

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Sone Ia-firma",
                "fiq_aga_sone": "1a",
            }
        )

    def _belop(self, grunnlag, brukt=0.0, aar=2026):
        # Grunnlaget sendes inn som parameter. Metoder paa Odoo-modeller kan
        # ikke overstyres paa en instans («object attribute is read-only»),
        # og en beregning som bare kan testes med ekte loennsslipper er
        # daarlig testbar uansett.
        #
        # 🔑 `fiq_aga_fribelop_aar` MAA settes sammen med forbruket. Uten det
        # ser aarsskifte-logikken et annet aar og nullstiller telleren — som
        # er RIKTIG oppfoersel, og som avslørte at disse testene manglet aaret.
        self.company.write(
            {
                "fiq_aga_fribelop_brukt": brukt,
                "fiq_aga_fribelop_aar": aar,
            }
        )
        slip = self.env["hr.payslip"].new(
            {
                "company_id": self.company.id,
                "date_to": f"{aar}-06-30",
            }
        )
        return slip.fiq_aga_belop(grunnlag=grunnlag)

    def test_07_under_fribelopet_gir_redusert_sats(self):
        # Besparelse = 1 000 000 x (14,1-10,6)% = 35 000 << 850 000.
        self.assertAlmostEqual(self._belop(1_000_000), 106_000.0, places=2)

    def test_08_oppbrukt_fribelop_gir_full_sats(self):
        self.assertAlmostEqual(
            self._belop(1_000_000, brukt=850_000),
            141_000.0,
            places=2,
        )

    def test_09_delvis_fribelop_splitter_grunnlaget(self):
        """Naar fribeloepet tar slutt MIDT i grunnlaget, skal den daekkede delen
        ha redusert sats og resten full sats."""
        # 10 000 igjen av fribeloepet daekker 10 000/0,035 = 285 714,29 grunnlag.
        belop = self._belop(1_000_000, brukt=840_000)
        forventet = 285_714.29 * 0.106 + (1_000_000 - 285_714.29) * 0.141
        self.assertAlmostEqual(belop, forventet, places=0)

    def test_10_sone_5_gir_null(self):
        self.company.fiq_aga_sone = "5"
        self.assertEqual(self._belop(1_000_000), 0.0)

    def test_10b_fjoraarets_forbruk_teller_ikke(self):
        """Fribeloepet er PER AAR. Et oppbrukt fribeloep fra i fjor skal ikke
        gi full sats i aar — da ville et sone Ia-foretak betalt full sats for
        resten av sin levetid etter foerste aar.

        Denne testen finnes fordi test_08 og test_09 feilet paa nettopp dette:
        de satte forbruket uten aaret, og aarsskifte-logikken nullstilte
        korrekt. Feilen var i testene, ikke i beregningen."""
        self.company.write(
            {
                "fiq_aga_fribelop_brukt": 850_000,
                "fiq_aga_fribelop_aar": 2025,
            }
        )
        slip = self.env["hr.payslip"].new(
            {
                "company_id": self.company.id,
                "date_to": "2026-06-30",
            }
        )
        # Fjoraarets forbruk er utdatert -> redusert sats gjelder igjen.
        self.assertAlmostEqual(
            slip.fiq_aga_belop(grunnlag=1_000_000),
            106_000.0,
            places=2,
        )


@tagged("post_install", "-at_install", "fiq")
class TestFribelopAarsskifte(TransactionCase):
    """Uten aarsskifte ville et foretak i sone Ia betalt full sats for resten
    av sin levetid etter foerste aar."""

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Årsskifte-firma",
                "fiq_aga_sone": "1a",
            }
        )

    def test_13_nytt_aar_gir_fullt_fribelop(self):
        self.company.write(
            {
                "fiq_aga_fribelop_brukt": 850_000,
                "fiq_aga_fribelop_aar": 2025,
            }
        )
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026),
            850_000,
            "Fribeløpet skal være helt tilbake i et nytt år.",
        )

    def test_14_samme_aar_beholder_forbruket(self):
        self.company.write(
            {
                "fiq_aga_fribelop_brukt": 300_000,
                "fiq_aga_fribelop_aar": 2026,
            }
        )
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026),
            550_000,
        )

    def test_15_forbruk_kan_ikke_bli_negativt(self):
        self.company.write(
            {
                "fiq_aga_fribelop_brukt": 900_000,
                "fiq_aga_fribelop_aar": 2026,
            }
        )
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026),
            0.0,
        )


@tagged("post_install", "-at_install", "fiq")
class TestStatusForpliktelser(TransactionCase):
    """🔑 Reist av 2.80 RGS: `mangler`-lista deres kunne ikke skille
    «ikke bygget» fra «bygget, men ingen data»."""

    def test_16_manglende_sone_gir_grunn_ikke_stillhet(self):
        company = self.env["res.company"].create({"name": "Uten sone"})
        status = (
            self.env["fiq.lonnsforpliktelse"]
            .with_company(company)
            .status_forpliktelser("2026-01-01", "2026-12-31")
        )
        self.assertFalse(status["aga"]["levert"])
        self.assertEqual(status["aga"]["grunn"], "mangler_sone")
        self.assertTrue(
            status["aga"]["forklaring"],
            "RGS skal få en forklaring de kan vise, ikke bare et flagg.",
        )

    def test_17_ikke_bygde_typer_er_merket(self):
        status = self.env["fiq.lonnsforpliktelse"].status_forpliktelser(
            "2026-01-01",
            "2026-12-31",
        )
        for type_ in ("lonn", "feriepenger", "otp"):
            self.assertEqual(status[type_]["grunn"], "ikke_bygget")

    def test_18_alle_fire_typene_har_status(self):
        # Speiler `mangler`-lista i fiq_gui_rgs. Mangler en type her, kan RGS
        # ikke avgjøre om den skal stå i lista.
        status = self.env["fiq.lonnsforpliktelse"].status_forpliktelser(
            "2026-01-01",
            "2026-12-31",
        )
        self.assertEqual(set(status), {"aga", "lonn", "feriepenger", "otp"})


@tagged("post_install", "-at_install", "fiq")
class TestOdoo19Tilstander(TransactionCase):
    """🔴 Fanger Odoo 18-navn som ser riktige ut men aldri matcher.

    Bakgrunn: aggregatet filtrerte paa state in ('done','paid','verify').
    'done' og 'verify' finnes IKKE i Odoo 19 — de heter 'validated' og
    'cancel'. Feilen ga ingen feilmelding; den ga bare FAERRE linjer, og
    validerte loennskjoeringer ville aldri naadd cashflow.

    Varselet kom fra 2.80 RGS 23.07: en test som laaser ÉN tilstandsverdi
    laaser ETT miljoe. Denne testen laaser i stedet at verdiene FINNES.
    """

    def test_19_tilstandene_vi_filtrerer_paa_finnes(self):
        felt = self.env["hr.payslip"]._fields["state"]
        gyldige = {verdi for verdi, _ in felt.selection}
        brukt = {"validated", "paid"}
        self.assertEqual(
            brukt - gyldige,
            set(),
            "Aggregatet filtrerer på tilstander som ikke finnes i denne "
            "Odoo-versjonen. Da blir cashflow stille tom, ikke rød.",
        )

    def test_20_gamle_odoo18_navn_er_borte(self):
        felt = self.env["hr.payslip"]._fields["state"]
        gyldige = {verdi for verdi, _ in felt.selection}
        self.assertEqual(
            gyldige & {"done", "verify"},
            set(),
            "Dukker Odoo 18-navnene opp igjen, må filteret vurderes på nytt.",
        )


@tagged("post_install", "-at_install", "fiq")
class TestLonnskostnad(TransactionCase):
    """Type 02 i den avtalte rekkefoelgen mot cashflow.

    🛡️ Bevis-vaktpost fra START denne gangen (grep fra 2.80 RGS): hver test
    som teller linjer bekrefter ogsaa BELOEPET, slik at en tom liste ikke kan
    passere som gront.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Lønnsfirma",
                "fiq_aga_sone": "2",
            }
        )
        struktur = self.env.ref("fiq_rgs_lonn.hr_payroll_structure_no_employee")
        self.slipper = self.env["hr.payslip"]
        for i in range(3):
            ansatt = self.env["hr.employee"].create(
                {
                    "name": f"Lønnsansatt {i}",
                    "company_id": self.company.id,
                }
            )
            slip = self.env["hr.payslip"].create(
                {
                    "name": f"Lønnsslipp {i}",
                    "employee_id": ansatt.id,
                    "company_id": self.company.id,
                    "date_from": "2026-08-01",
                    "date_to": "2026-08-31",
                    "struct_id": struktur.id,
                }
            )
            # net_wage er et LAGRET felt (som `total` paa linja) — det fylles
            # av compute_sheet(). Settes eksplisitt her, jf. laerdommen fra AGA.
            slip.net_wage = 30000.0
            self.slipper |= slip

    def _lonnslinjer(self):
        return [
            linje
            for linje in self.env["fiq.lonnsforpliktelse"]
            .with_company(self.company)
            .hent_lonnsforpliktelser("2026-01-01", "2026-12-31")
            if linje["type"] == "lonn"
        ]

    def test_27_augustlonn_forfaller_15_september(self):
        """🔑 Forfall og periode SPRIKER systematisk — det er hele grunnen til
        at `periode`-feltet finnes. Riktig for likviditeten, forklarlig for
        leseren."""
        self.slipper.write({"state": "paid"})
        linjer = self._lonnslinjer()
        self.assertEqual(len(linjer), 1, "Én linje per utbetaling.")
        self.assertEqual(linjer[0]["forfall"].month, 9)
        self.assertEqual(linjer[0]["forfall"].day, 15)
        self.assertEqual(linjer[0]["periode"], "August 2026")

    def test_28_belopet_er_NETTO_ikke_brutto(self):
        """🛡️ Bevis-vaktpost: 3 x 30 000 netto = 90 000.

        Brukte vi brutto, ville forskuddstrekket blitt talt to ganger naar
        skattetrekk senere legges inn som egen forpliktelsestype.
        """
        self.slipper.write({"state": "paid"})
        linjer = self._lonnslinjer()
        self.assertTrue(linjer, "Ingen lønnslinjer å måle på.")
        self.assertAlmostEqual(
            sum(linje["belop"] for linje in linjer),
            90_000.0,
            2,
            "Beløpet er ikke summen av nettolønn — testen måler noe annet "
            "enn den tror.",
        )

    def test_29_desemberlonn_forfaller_i_januar_neste_aar(self):
        """Aarsskiftet i forfallsberegningen. Uten det ville desemberlønn
        forfalt 15. maaned 13."""
        self.slipper.write(
            {
                "date_from": "2026-12-01",
                "date_to": "2026-12-31",
                "state": "paid",
            }
        )
        linjer = self._lonnslinjer()
        self.assertTrue(linjer)
        self.assertEqual(linjer[0]["forfall"].year, 2027)
        self.assertEqual(linjer[0]["forfall"].month, 1)

    def test_30_validert_er_planlagt_utbetalt_er_bokfort(self):
        """Samme skille som for AGA — og det MAA holdes her, fordi 2.80 RGS
        viser det vi sender uten aa overproeve det."""
        self.slipper.write({"state": "validated"})
        self.assertTrue(
            all(linje["sikkerhet"] == "planlagt" for linje in self._lonnslinjer())
        )
        self.slipper.write({"state": "paid"})
        self.assertTrue(
            all(linje["sikkerhet"] == "bokfort" for linje in self._lonnslinjer())
        )

    def test_31_status_og_linjer_er_enige(self):
        """🤝 Kryss-testen — motstykket til 2.80 RGS' egen. Bygget FRA START
        denne gangen, ikke etterpaa."""
        self.slipper.write({"state": "paid"})
        status = (
            self.env["fiq.lonnsforpliktelse"]
            .with_company(self.company)
            .status_forpliktelser("2026-01-01", "2026-12-31")
        )
        self.assertEqual(
            bool(self._lonnslinjer()),
            status["lonn"]["levert"],
            "status_forpliktelser() og aggregatet spriker — kontrakten er "
            "brutt selv om begge sider ser riktige ut hver for seg.",
        )

    def test_32_faerre_enn_tre_ansatte_gir_ingen_linje(self):
        """🔒 Re-identifiseringsgrensen gjelder ogsaa loennskostnad."""
        self.slipper.write({"state": "paid"})
        self.assertTrue(self._lonnslinjer())
        self.slipper[0].state = "draft"
        self.assertEqual(self._lonnslinjer(), [])


@tagged("post_install", "-at_install", "fiq")
class TestFeriepenger(TransactionCase):
    """Type 03. Satsene er ferieloven § 10, verifisert mot lovdata + skatteetaten.

    🔴 Den vanskeligste typen: SATSEN AVHENGER AV ALDER, og alder er
    personopplysning. Beregningen skjer i HR; bare summen forlater modulen.
    """

    def setUp(self):
        super().setUp()
        from datetime import date

        self.date = date
        self.company = self.env["res.company"].create(
            {
                "name": "Feriefirma",
                "fiq_aga_sone": "2",
            }
        )
        self.struktur = self.env.ref("fiq_rgs_lonn.hr_payroll_structure_no_employee")

    def _slip(self, fodselsaar=1990, fem_uker=False, aar=2026):
        vals = {"name": "Ferieansatt", "company_id": self.company.id}
        if fodselsaar:
            vals["birthday"] = f"{fodselsaar}-03-15"
        ansatt = self.env["hr.employee"].create(vals)
        slip = self.env["hr.payslip"].create(
            {
                "name": "Slipp",
                "employee_id": ansatt.id,
                "company_id": self.company.id,
                "date_from": f"{aar}-01-01",
                "date_to": f"{aar}-01-31",
                "struct_id": self.struktur.id,
            }
        )
        slip.version_id.fiq_ferie_fem_uker = fem_uker
        return slip

    def _param(self, kode, aar=2026, mnd=6):
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            kode, self.date(aar, mnd, 1)
        )

    def test_33_satsene_stemmer_med_ferieloven(self):
        self.assertEqual(
            self._param("no_feriepenger_satser"),
            {
                "ordinaer": 10.2,
                "fem_uker": 12.0,
                "over_60": 12.5,
                "over_60_fem_uker": 14.3,
            },
            "Satsene er ferieloven § 10 — ikke en preferanse.",
        )

    def test_34_ordinaer_sats_er_10_2(self):
        self.assertEqual(self._slip().fiq_feriepenger_sats(2026), 10.2)

    def test_35_fem_uker_gir_12(self):
        self.assertEqual(self._slip(fem_uker=True).fiq_feriepenger_sats(2026), 12.0)

    def test_36_over_60_gir_12_5(self):
        # Foedt 1966 → fyller 60 i 2026.
        self.assertEqual(self._slip(fodselsaar=1966).fiq_feriepenger_sats(2026), 12.5)

    def test_37_fyller_60_I_LOPET_av_aaret_teller(self):
        """🔑 «Over 60» er IKKE alder paa utbetalingsdagen. Retten gjelder fra
        og med AARET arbeidstakeren fyller 60 — en som fyller 60 i desember
        skal ha forhoeyet sats hele det aaret."""
        slip = self._slip(fodselsaar=1966)
        slip.employee_id.birthday = "1966-12-31"
        self.assertEqual(
            slip.fiq_feriepenger_sats(2026),
            12.5,
            "Fyller 60 i desember — skal ha forhøyet sats fra januar.",
        )

    def test_38_manglende_fodselsdato_gir_ORDINAER_sats(self):
        """Det forsiktige valget. Aa gjette paa hoeyere sats ville gitt for
        stor avsetning — og gjetning er forbudt naar grunnlaget er juridisk
        bindende."""
        self.assertEqual(self._slip(fodselsaar=None).fiq_feriepenger_sats(2026), 10.2)

    def test_39_avsetning_under_60(self):
        """🛡️ Bevis-vaktpost: 500 000 x 10,2 % = 51 000."""
        self.assertAlmostEqual(
            self._slip().fiq_feriepenger_avsetning(500_000, 2026),
            51_000.0,
            2,
            "Avsetningen er ikke grunnlag x sats — testen måler noe annet.",
        )

    def test_40_over_60_under_6G_faar_full_forhoyet_sats(self):
        # 6 G for 2026 = 819 294. Grunnlag 500 000 ligger under taket.
        self.assertAlmostEqual(
            self._slip(fodselsaar=1966).fiq_feriepenger_avsetning(500_000, 2026),
            62_500.0,
            2,  # 500 000 x 12,5 %
        )

    def test_41_over_60_OVER_6G_splitter_ved_taket(self):
        """🔑 Ferieloven § 10: tillegget gjelder KUN opp til 6 G. Over taket
        brukes ordinaer sats paa det overskytende."""
        tak = self._param("no_feriepenger_6g")
        forventet = tak * 0.125 + 100_000 * 0.102
        self.assertAlmostEqual(
            self._slip(fodselsaar=1966).fiq_feriepenger_avsetning(tak + 100_000, 2026),
            forventet,
            2,
        )

    def test_42_6g_folger_opptjeningsaaret(self):
        """G justeres 1. mai hvert aar. Grensen for feriepenger opptjent i
        2025 er 6 G per 31.12.2025 — ikke dagens G."""
        g2025 = self._param("no_feriepenger_6g", aar=2025)
        g2026 = self._param("no_feriepenger_6g", aar=2026)
        self.assertEqual(g2025, 780960)
        self.assertEqual(g2026, 819294)
        self.assertNotEqual(g2025, g2026, "G endres årlig — begge må finnes.")


@tagged("post_install", "-at_install", "fiq")
class TestOtp(TransactionCase):
    """Type 04 — obligatorisk tjenestepensjon (OTP-loven § 4).

    🔑 «Pensjon fra foerste krone og dag» (2021) fjernet 20 %-stillingsgrensen
    og senket aldersgrensen fra 20 til 13 aar. Bygger man paa en eldre
    beskrivelse, faar deltidsansatte og unge INGEN pensjon — uten feilmelding.
    """

    def setUp(self):
        super().setUp()
        from datetime import date

        self.date = date
        self.company = self.env["res.company"].create(
            {
                "name": "Pensjonsfirma",
                "fiq_aga_sone": "2",
            }
        )
        self.struktur = self.env.ref("fiq_rgs_lonn.hr_payroll_structure_no_employee")

    def _slip(self, fodselsaar=1990, aar=2026):
        vals = {"name": "Pensjonsansatt", "company_id": self.company.id}
        if fodselsaar:
            vals["birthday"] = f"{fodselsaar}-03-15"
        ansatt = self.env["hr.employee"].create(vals)
        return self.env["hr.payslip"].create(
            {
                "name": "Slipp",
                "employee_id": ansatt.id,
                "company_id": self.company.id,
                "date_from": f"{aar}-01-01",
                "date_to": f"{aar}-01-31",
                "struct_id": self.struktur.id,
            }
        )

    def _param(self, kode, aar=2026, mnd=6):
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            kode, self.date(aar, mnd, 1)
        )

    def test_43_minstesatsen_er_2_prosent(self):
        """OTP-loven § 4 — lovens gulv."""
        self.assertEqual(self._param("no_otp_minstesats"), 2.0)

    def test_44_tomt_selskapsfelt_gir_lovens_minstekrav(self):
        self.assertEqual(self._slip().fiq_otp_sats(), 2.0)

    def test_45_selskapets_egen_sats_overstyrer(self):
        self.company.fiq_otp_sats = 5.0
        self.assertEqual(self._slip().fiq_otp_sats(), 5.0)

    def test_46_sats_UNDER_lovens_minstekrav_avvises(self):
        """🛑 Uten denne sperren kunne noen satt 1 % i god tro — og foretaket
        ville brutt loven uten at noe feilet."""
        from odoo.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            self.company.fiq_otp_sats = 1.0

    def test_47_innskudd_under_taket(self):
        """🛡️ Bevis-vaktpost: 500 000 x 2 % = 10 000."""
        self.assertAlmostEqual(
            self._slip().fiq_otp_innskudd(500_000),
            10_000.0,
            2,
            "Innskuddet er ikke grunnlag x sats — testen måler noe annet.",
        )

    def test_48_innskudd_kappes_ved_12G(self):
        """OTP-loven § 4: innskuddet beregnes av loenn OPP TIL 12 G.
        Loenn over taket gir ingen pliktig innskudd."""
        tak = self._param("no_otp_12g")
        over = self._slip().fiq_otp_innskudd(tak + 500_000)
        paa = self._slip().fiq_otp_innskudd(tak)
        self.assertAlmostEqual(over, paa, 2, "Lønn over 12 G skal ikke telle.")

    def test_49_ung_ansatt_UNDER_13_er_ikke_omfattet(self):
        # Foedt 2015 → fyller 11 i 2026.
        self.assertFalse(self._slip(fodselsaar=2015).fiq_otp_omfattet())

    def test_50_ansatt_som_fyller_13_ER_omfattet(self):
        """🔑 Aldersgrensen er 13 aar, ikke 20. Ble senket ved «pensjon fra
        foerste krone og dag» — en eldre beskrivelse ville utelatt unge."""
        self.assertTrue(self._slip(fodselsaar=2013).fiq_otp_omfattet())

    def test_51_manglende_fodselsdato_gir_MEDLEMSKAP(self):
        """Det forsiktige valget peker MOTSATT vei her enn for feriepenger:
        aa utelate noen fra pensjonsordningen er verre enn aa avsette for mye."""
        self.assertTrue(self._slip(fodselsaar=None).fiq_otp_omfattet())

    def test_52_ikke_omfattet_gir_null_innskudd(self):
        self.assertEqual(self._slip(fodselsaar=2015).fiq_otp_innskudd(500_000), 0.0)

    def test_53_12g_folger_aaret(self):
        """G justeres 1. mai — taket maa finnes for hvert aar."""
        self.assertEqual(self._param("no_otp_12g", aar=2025), 1561920)
        self.assertEqual(self._param("no_otp_12g", aar=2026), 1638588)


@tagged("post_install", "-at_install", "fiq")
class TestPersonvern(TransactionCase):
    """🔒 Re-identifiseringsgrensen. 2.80 RGS har bedt om aa bli holdt til den."""

    def test_11_aggregatet_har_ingen_persondata(self):
        felt_som_aldri_skal_finnes = {
            "employee_id",
            "employee",
            "navn",
            "name",
            "res_id",
        }
        linjer = self.env["fiq.lonnsforpliktelse"].hent_lonnsforpliktelser(
            "2026-01-01",
            "2026-12-31",
        )
        for linje in linjer:
            self.assertFalse(
                felt_som_aldri_skal_finnes & set(linje),
                f"Aggregatet lekker persondata: {linje}",
            )

    def test_12_kontraktens_felter_er_komplette(self):
        paakrevd = {
            "type",
            "label",
            "forfall",
            "belop",
            "sikkerhet",
            "kilde",
            "periode",
        }
        for linje in self.env["fiq.lonnsforpliktelse"].hent_lonnsforpliktelser(
            "2026-01-01",
            "2026-12-31",
        ):
            self.assertEqual(
                paakrevd - set(linje),
                set(),
                "Kontrakten med 2.80 RGS krever alle sju feltene.",
            )


@tagged("post_install", "-at_install", "fiq")
class TestKontraktMedEkteData(TransactionCase):
    """🔴 Testene over itererer over en TOM liste og passerer uansett.

    2.80 RGS meldte 23.07 at 26 gronne tester skjulte en DOED kobling: de
    testet at `mangler` hadde riktig FORM, ingen sammenlignet svaret med
    2.20s faktiske status. «Virker, men galt» er den verste klassen i dette
    loepet.

    Samme svakhet var her: uten loennsslipper i basen beviser test_11 og
    test_12 ingenting. Denne klassen lager ekte data foerst.
    """

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create(
            {
                "name": "Kontraktfirma",
                "fiq_aga_sone": "2",  # 10,6 % — ingen fribeloepsmekanikk
            }
        )
        struktur = self.env.ref("fiq_rgs_lonn.hr_payroll_structure_no_employee")
        # Tre ansatte: under grensen ville linja blitt utelatt (GDPR).
        self.slipper = self.env["hr.payslip"]
        for i in range(3):
            ansatt = self.env["hr.employee"].create(
                {
                    "name": f"Testansatt {i}",
                    "company_id": self.company.id,
                }
            )
            slip = self.env["hr.payslip"].create(
                {
                    "name": f"Slipp {i}",
                    "employee_id": ansatt.id,
                    "company_id": self.company.id,
                    "date_from": "2026-01-01",
                    "date_to": "2026-01-31",
                    "struct_id": struktur.id,
                }
            )
            # Loennslinjer MAA finnes — uten dem er grunnlaget 0 og aggregatet
            # gir ingen linjer. Det var nettopp det testene avslørte foerste
            # gang: beregningen leste linjer som ingenting skrev.
            self.env["hr.payslip.line"].create(
                {
                    "name": "Grunnlønn",
                    "code": "BASIC",
                    # salary_rule_id er PAAKREVD (NOT NULL) — en loennslinje maa
                    # peke paa loennsarten som skapte den. `category_id` settes
                    # IKKE her: det er et `related`-felt fra loennsarten og ville
                    # blitt overstyrt uansett.
                    "salary_rule_id": self.env.ref("fiq_rgs_lonn.rule_no_basic").id,
                    "employee_id": ansatt.id,
                    "slip_id": slip.id,
                    "amount": 40000.0,
                    "quantity": 1.0,
                    "rate": 100.0,
                    # 🔑 `total` er et LAGRET felt, ikke beregnet — det fylles av
                    # loennsmotoren under `compute_sheet()`. Opprettes linja
                    # direkte, maa total settes eksplisitt, ellers er den 0 og
                    # grunnlaget blir null. Det var derfor testene ga tomme lister.
                    "total": 40000.0,
                }
            )
            self.slipper |= slip

    def _linjer(self):
        return (
            self.env["fiq.lonnsforpliktelse"]
            .with_company(self.company)
            .hent_lonnsforpliktelser("2026-01-01", "2026-12-31")
        )

    def test_21_draft_slipper_gir_ingen_linjer(self):
        """Utkast er ikke en forpliktelse. Kommer de med, blaeses cashflow opp."""
        self.assertEqual(self._linjer(), [])

    def test_22_validerte_slipper_gir_linjer_merket_planlagt(self):
        """🔑 Testen som ville fanget Odoo 18-tilstanden.

        Med filteret ('done','paid','verify') ga dette 0 linjer — stille, uten
        feilmelding. Her feiler den hoeylytt i stedet.
        """
        self.slipper.write({"state": "validated"})
        linjer = self._linjer()
        self.assertTrue(
            linjer,
            "Validerte lønnskjøringer nådde ikke cashflow. Sjekk at "
            "tilstandsnavnene i filteret finnes i denne Odoo-versjonen.",
        )
        for linje in linjer:
            self.assertEqual(
                linje["sikkerhet"],
                "planlagt",
                "Bekreftet, men ikke utbetalt lønn er PLANLAGT — ikke bokført.",
            )

    def test_23_utbetalte_slipper_er_bokfort(self):
        self.slipper.write({"state": "paid"})
        for linje in self._linjer():
            self.assertEqual(linje["sikkerhet"], "bokfort")

    def test_24_alle_sju_feltene_paa_EKTE_linjer(self):
        """Det test_12 skulle bevist, men ikke gjorde uten data.

        🛡️ VAKTPOST (grep fra 2.80 RGS 23.07): en test som itererer over
        ingenting ser IDENTISK ut med en som passerer. Derfor bekreftes det
        eksplisitt at det FINNES data, og at beloepet er det forventede —
        ikke bare at feltene er der.
        """
        self.slipper.write({"state": "paid"})
        linjer = self._linjer()
        self.assertTrue(linjer, "Ingen linjer å teste kontrakten mot.")
        # 3 ansatte x 40 000 = 120 000 grunnlag, sone II = 10,6 %
        self.assertAlmostEqual(
            sum(linje["belop"] for linje in linjer),
            12_720.0,
            2,
            "Beløpet er ikke det grunnlaget tilsier — testen måler noe annet "
            "enn den tror.",
        )
        paakrevd = {
            "type",
            "label",
            "forfall",
            "belop",
            "sikkerhet",
            "kilde",
            "periode",
        }
        for linje in linjer:
            self.assertEqual(paakrevd - set(linje), set())
            self.assertEqual(linje["kilde"], "Odoo")
            self.assertEqual(linje["forfall"].day, 15, "AGA forfaller den 15.")

    def test_25_status_og_linjer_er_enige(self):
        """🤝 Motstykket til RGS' kryss-test: sier status at vi leverer,
        MÅ det finnes linjer — og omvendt. Spriker de, er kontrakten brutt
        selv om begge sider ser riktige ut hver for seg."""
        self.slipper.write({"state": "paid"})
        modell = self.env["fiq.lonnsforpliktelse"].with_company(self.company)
        status = modell.status_forpliktelser("2026-01-01", "2026-12-31")
        linjer = [linje for linje in self._linjer() if linje["type"] == "aga"]
        self.assertEqual(
            bool(linjer),
            status["aga"]["levert"],
            "status_forpliktelser() sier «{}», men aggregatet ga {} AGA-linjer.".format(
                status["aga"]["levert"], len(linjer)
            ),
        )

    def test_26_faerre_enn_tre_ansatte_gir_ingen_linje(self):
        """🔒 Re-identifiseringsgrensen, testet med EKTE data."""
        self.slipper.write({"state": "paid"})
        self.assertTrue(self._linjer(), "Tre ansatte skal gi linjer.")

        # Ta én slipp UT av utvalget ved å sette den tilbake til utkast.
        # `unlink()` ville vært mer direkte, men sletting av en lønnsslipp
        # utløser meldingssporing (mail.thread) som feiler i testkontekst —
        # og den mekanikken er ikke det denne testen skal måle.
        self.slipper[0].state = "draft"
        self.assertEqual(
            self._linjer(),
            [],
            "En sum for under tre ansatte er personopplysning selv uten navn.",
        )
