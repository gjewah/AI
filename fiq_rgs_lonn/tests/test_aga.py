# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAgaSatser(TransactionCase):
    """Satsene er juridisk bindende. Testene sjekker at TALLENE stemmer med
    Stortingsvedtak FOR-2025-12-18-2748 § 3 — ikke bare at koden kjoerer."""

    def _sats(self, kode):
        # _get_parameter_from_code kalles paa MODELLEN, ikke paa en post
        # (verifisert i hr_payroll/models/hr_rule_parameter.py:75).
        # Datoen avgjoer hvilken versjon av satsen som gjelder.
        from datetime import date
        return self.env["hr.rule.parameter"]._get_parameter_from_code(
            kode, date(2026, 6, 1),
        )

    def test_01_alle_syv_soner_finnes(self):
        satser = self._sats("no_aga_sonesatser")
        self.assertEqual(
            sorted(satser), ["1", "1a", "2", "3", "4", "4a", "5"],
            "Norge har sju AGA-soner. Mangler en, blir loennskjoeringen feil "
            "for alle i den sonen.",
        )

    def test_02_satsene_stemmer_med_stortingsvedtaket(self):
        # Kilde: FOR-2025-12-18-2748 § 3 foerste ledd, bekreftet mot
        # skatteetaten.no/satser/arbeidsgiveravgift.
        fasit = {"1": 14.1, "1a": 10.6, "2": 10.6, "3": 6.4,
                 "4": 5.1, "4a": 7.9, "5": 0.0}
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


@tagged("post_install", "-at_install")
class TestAgaSone(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({
            "name": "Testfirma AGA",
            "fiq_aga_sone": "2",
        })

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


@tagged("post_install", "-at_install")
class TestAgaFribelop(TransactionCase):
    """Sone Ia er IKKE en ren sats — redusert sats gjelder bare til fribeloepet
    er brukt opp. Det er den vanskeligste delen av regelverket."""

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({
            "name": "Sone Ia-firma",
            "fiq_aga_sone": "1a",
        })

    def _belop(self, grunnlag, brukt=0.0, aar=2026):
        # Grunnlaget sendes inn som parameter. Metoder paa Odoo-modeller kan
        # ikke overstyres paa en instans («object attribute is read-only»),
        # og en beregning som bare kan testes med ekte loennsslipper er
        # daarlig testbar uansett.
        #
        # 🔑 `fiq_aga_fribelop_aar` MAA settes sammen med forbruket. Uten det
        # ser aarsskifte-logikken et annet aar og nullstiller telleren — som
        # er RIKTIG oppfoersel, og som avslørte at disse testene manglet aaret.
        self.company.write({
            "fiq_aga_fribelop_brukt": brukt,
            "fiq_aga_fribelop_aar": aar,
        })
        slip = self.env["hr.payslip"].new({
            "company_id": self.company.id,
            "date_to": "%s-06-30" % aar,
        })
        return slip.fiq_aga_belop(grunnlag=grunnlag)

    def test_07_under_fribelopet_gir_redusert_sats(self):
        # Besparelse = 1 000 000 x (14,1-10,6)% = 35 000 << 850 000.
        self.assertAlmostEqual(self._belop(1_000_000), 106_000.0, places=2)

    def test_08_oppbrukt_fribelop_gir_full_sats(self):
        self.assertAlmostEqual(
            self._belop(1_000_000, brukt=850_000), 141_000.0, places=2,
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
        self.company.write({
            "fiq_aga_fribelop_brukt": 850_000,
            "fiq_aga_fribelop_aar": 2025,
        })
        slip = self.env["hr.payslip"].new({
            "company_id": self.company.id,
            "date_to": "2026-06-30",
        })
        # Fjoraarets forbruk er utdatert -> redusert sats gjelder igjen.
        self.assertAlmostEqual(
            slip.fiq_aga_belop(grunnlag=1_000_000), 106_000.0, places=2,
        )


@tagged("post_install", "-at_install")
class TestFribelopAarsskifte(TransactionCase):
    """Uten aarsskifte ville et foretak i sone Ia betalt full sats for resten
    av sin levetid etter foerste aar."""

    def setUp(self):
        super().setUp()
        self.company = self.env["res.company"].create({
            "name": "Årsskifte-firma",
            "fiq_aga_sone": "1a",
        })

    def test_13_nytt_aar_gir_fullt_fribelop(self):
        self.company.write({
            "fiq_aga_fribelop_brukt": 850_000,
            "fiq_aga_fribelop_aar": 2025,
        })
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026), 850_000,
            "Fribeløpet skal være helt tilbake i et nytt år.",
        )

    def test_14_samme_aar_beholder_forbruket(self):
        self.company.write({
            "fiq_aga_fribelop_brukt": 300_000,
            "fiq_aga_fribelop_aar": 2026,
        })
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026), 550_000,
        )

    def test_15_forbruk_kan_ikke_bli_negativt(self):
        self.company.write({
            "fiq_aga_fribelop_brukt": 900_000,
            "fiq_aga_fribelop_aar": 2026,
        })
        self.assertEqual(
            self.company.fiq_aga_fribelop_gjenstaaende(850_000, 2026), 0.0,
        )


@tagged("post_install", "-at_install")
class TestStatusForpliktelser(TransactionCase):
    """🔑 Reist av 2.80 RGS: `mangler`-lista deres kunne ikke skille
    «ikke bygget» fra «bygget, men ingen data»."""

    def test_16_manglende_sone_gir_grunn_ikke_stillhet(self):
        company = self.env["res.company"].create({"name": "Uten sone"})
        status = self.env["fiq.lonnsforpliktelse"].with_company(
            company
        ).status_forpliktelser("2026-01-01", "2026-12-31")
        self.assertFalse(status["aga"]["levert"])
        self.assertEqual(status["aga"]["grunn"], "mangler_sone")
        self.assertTrue(
            status["aga"]["forklaring"],
            "RGS skal få en forklaring de kan vise, ikke bare et flagg.",
        )

    def test_17_ikke_bygde_typer_er_merket(self):
        status = self.env["fiq.lonnsforpliktelse"].status_forpliktelser(
            "2026-01-01", "2026-12-31",
        )
        for type_ in ("lonn", "feriepenger", "otp"):
            self.assertEqual(status[type_]["grunn"], "ikke_bygget")

    def test_18_alle_fire_typene_har_status(self):
        # Speiler `mangler`-lista i fiq_gui_rgs. Mangler en type her, kan RGS
        # ikke avgjøre om den skal stå i lista.
        status = self.env["fiq.lonnsforpliktelse"].status_forpliktelser(
            "2026-01-01", "2026-12-31",
        )
        self.assertEqual(set(status), {"aga", "lonn", "feriepenger", "otp"})


@tagged("post_install", "-at_install")
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
            brukt - gyldige, set(),
            "Aggregatet filtrerer på tilstander som ikke finnes i denne "
            "Odoo-versjonen. Da blir cashflow stille tom, ikke rød.",
        )

    def test_20_gamle_odoo18_navn_er_borte(self):
        felt = self.env["hr.payslip"]._fields["state"]
        gyldige = {verdi for verdi, _ in felt.selection}
        self.assertEqual(
            gyldige & {"done", "verify"}, set(),
            "Dukker Odoo 18-navnene opp igjen, må filteret vurderes på nytt.",
        )


@tagged("post_install", "-at_install")
class TestPersonvern(TransactionCase):
    """🔒 Re-identifiseringsgrensen. 2.80 RGS har bedt om aa bli holdt til den."""

    def test_11_aggregatet_har_ingen_persondata(self):
        felt_som_aldri_skal_finnes = {"employee_id", "employee", "navn", "name", "res_id"}
        linjer = self.env["fiq.lonnsforpliktelse"].hent_lonnsforpliktelser(
            "2026-01-01", "2026-12-31",
        )
        for linje in linjer:
            self.assertFalse(
                felt_som_aldri_skal_finnes & set(linje),
                "Aggregatet lekker persondata: %s" % linje,
            )

    def test_12_kontraktens_felter_er_komplette(self):
        paakrevd = {"type", "label", "forfall", "belop", "sikkerhet", "kilde", "periode"}
        for linje in self.env["fiq.lonnsforpliktelse"].hent_lonnsforpliktelser(
            "2026-01-01", "2026-12-31",
        ):
            self.assertEqual(
                paakrevd - set(linje), set(),
                "Kontrakten med 2.80 RGS krever alle sju feltene.",
            )
