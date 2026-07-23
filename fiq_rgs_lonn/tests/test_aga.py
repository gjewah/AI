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

    def _belop(self, grunnlag, brukt=0.0):
        self.company.fiq_aga_fribelop_brukt = brukt
        slip = self.env["hr.payslip"].new({"company_id": self.company.id})
        slip.fiq_aga_grunnlag = lambda: grunnlag
        return slip.fiq_aga_belop()

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
