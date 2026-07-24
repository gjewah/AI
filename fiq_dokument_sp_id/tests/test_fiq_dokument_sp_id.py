"""Tester som OPPRETTER sin egen tilstand (PORT 6, brain/00_FERDIG.md).

En test som bare leser eksisterende data kan ikke bevise fravær av data-betingede
krasj. Hver test her lager postene den trenger.
"""

import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq")
class TestFiqDokumentSpId(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.prosjekt = cls.env["project.project"].create(
            {"name": "TEST SP-ID prosjekt"}
        )
        cls.oppgave = cls.env["project.task"].create(
            {
                "name": "TEST SP-ID oppgave",
                "project_id": cls.prosjekt.id,
            }
        )
        cls.dok = cls.env["documents.document"].create(
            {
                "name": "TEST SP-ID dokument",
                "datas": base64.b64encode(b"innhold"),
            }
        )

    # ------------------------------------------------------------------
    # Dokument
    # ------------------------------------------------------------------
    def test_dokument_uten_referanse(self):
        """Nytt dokument har ingen SP-referanse — flagget skal være av."""
        self.assertFalse(self.dok.sp_drive_id)
        self.assertFalse(self.dok.sp_item_id)
        self.assertFalse(self.dok.sp_har_referanse)

    def test_sett_sp_referanse(self):
        self.dok.sett_sp_referanse("b!DRIVE123", "01ITEM456", "https://sp/fil.pdf")
        self.assertEqual(self.dok.sp_drive_id, "b!DRIVE123")
        self.assertEqual(self.dok.sp_item_id, "01ITEM456")
        self.assertEqual(self.dok.sp_web_url, "https://sp/fil.pdf")
        self.assertTrue(self.dok.sp_har_referanse)
        self.assertTrue(self.dok.sp_sist_synk, "sist synk skal settes automatisk")

    def test_referanse_uten_drive_avvises(self):
        """Item-ID alene er ikke entydig — skal nektes."""
        with self.assertRaises(UserError):
            self.dok.sett_sp_referanse(False, "01ITEM456")

    def test_referanse_uten_item_avvises(self):
        with self.assertRaises(UserError):
            self.dok.sett_sp_referanse("b!DRIVE123", False)

    def test_web_url_er_valgfri(self):
        self.dok.sett_sp_referanse("b!D", "01I")
        self.assertTrue(self.dok.sp_har_referanse)
        self.assertFalse(self.dok.sp_web_url)

    def test_finn_pa_referanse(self):
        self.dok.sett_sp_referanse("b!DRIVE_X", "01ITEM_X")
        funnet = self.env["documents.document"].finn_pa_sp_referanse(
            "b!DRIVE_X", "01ITEM_X"
        )
        self.assertEqual(funnet, self.dok)

    def test_finn_uten_treff_gir_tom(self):
        funnet = self.env["documents.document"].finn_pa_sp_referanse(
            "b!FINNES_IKKE", "01X"
        )
        self.assertFalse(funnet)

    def test_finn_med_tomme_argumenter(self):
        """Skal returnere tomt, ikke krasje eller matche vilkårlig."""
        self.assertFalse(
            self.env["documents.document"].finn_pa_sp_referanse(False, False)
        )

    def test_samme_item_id_i_ulike_biblioteker(self):
        """Item-ID kan gjentas på tvers av drives — begge skal kunne lagres."""
        dok2 = self.env["documents.document"].create(
            {
                "name": "TEST SP-ID dokument 2",
                "datas": base64.b64encode(b"innhold2"),
            }
        )
        self.dok.sett_sp_referanse("b!DRIVE_A", "01SAMME")
        dok2.sett_sp_referanse("b!DRIVE_B", "01SAMME")
        self.assertTrue(self.dok.sp_har_referanse)
        self.assertTrue(dok2.sp_har_referanse)

    def test_url_feltet_rores_ikke(self):
        """Loym-feltet `url` skal stå urørt — det er sikkerheten Gjermund ba om."""
        self.dok.url = "https://sp/gammel-mappe-url"
        self.dok.sett_sp_referanse("b!D", "01I", "https://sp/ny.pdf")
        self.assertEqual(self.dok.url, "https://sp/gammel-mappe-url")

    # ------------------------------------------------------------------
    # Oppgave
    # ------------------------------------------------------------------
    def test_oppgave_uten_mappe(self):
        self.assertFalse(self.oppgave.sp_har_mappe)

    def test_sett_sp_mappe_paa_oppgave(self):
        self.oppgave.sett_sp_mappe("b!D", "01MAPPE", "https://sp/mappe", "26_052 Test")
        self.assertTrue(self.oppgave.sp_har_mappe)
        self.assertEqual(self.oppgave.sp_mappenavn, "26_052 Test")

    def test_oppgave_mappe_krever_begge_id(self):
        with self.assertRaises(UserError):
            self.oppgave.sett_sp_mappe("b!D", False)

    def test_foreslatt_mappenavn(self):
        navn = self.oppgave.foreslatt_mappenavn()
        self.assertIn("TEST SP-ID oppgave", navn)
        self.assertTrue(navn, "skal aldri være tomt")

    def test_mappenavn_fjerner_ugyldige_tegn(self):
        """Tegn som ikke er lovlige i filnavn må bort — ellers feiler Graph-kallet."""
        self.oppgave.name = 'Bad/Vask: 50% "test" <ny>'
        navn = self.oppgave.foreslatt_mappenavn()
        for tegn in '\\/:*?"<>|':
            self.assertNotIn(tegn, navn, f"ugyldig tegn {tegn!r} ble ikke fjernet")

    def test_mappenavn_uten_punktum_i_endene(self):
        """SharePoint nekter navn som starter eller slutter med punktum."""
        self.oppgave.name = ".skjult navn."
        navn = self.oppgave.foreslatt_mappenavn()
        self.assertFalse(navn.startswith("."))
        self.assertFalse(navn.endswith("."))

    def test_mappenavn_kappes(self):
        self.oppgave.name = "A" * 400
        self.assertLessEqual(len(self.oppgave.foreslatt_mappenavn()), 120)

    # ------------------------------------------------------------------
    # Prosjekt
    # ------------------------------------------------------------------
    def test_prosjekt_uten_mappe(self):
        self.assertFalse(self.prosjekt.sp_har_mappe)

    def test_sett_sp_mappe_paa_prosjekt(self):
        self.prosjekt.sett_sp_mappe("b!D", "01PRJMAPPE", "https://sp/prosjekt")
        self.assertTrue(self.prosjekt.sp_har_mappe)
        self.assertEqual(self.prosjekt.sp_mappe_url, "https://sp/prosjekt")

    def test_prosjekt_mappe_krever_begge_id(self):
        with self.assertRaises(UserError):
            self.prosjekt.sett_sp_mappe(False, "01X")

    def test_prosjekt_og_oppgave_er_uavhengige(self):
        """Å sette mappe på prosjektet skal ikke røre oppgavens felt."""
        self.prosjekt.sett_sp_mappe("b!D", "01PRJ")
        self.assertTrue(self.prosjekt.sp_har_mappe)
        self.assertFalse(self.oppgave.sp_har_mappe)
