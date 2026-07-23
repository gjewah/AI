# -*- coding: utf-8 -*-
"""Tester for spor-tilhørighet — ingen økt skal være hjemløs i stillhet.

Bakgrunn (Gjermund 20.07.2026): øktnummer-kaoset kostet over 100 timer.
Sporet er den varige enheten; økter er arbeidsperioder i den. Disse testene
vokter de tre mekanismene som gjør at det faktisk HOLDER i praksis:

  1. kodenormalisering  — «gui kr» og «Kontrollrom» må bli SAMME spor
  2. hjemløs-fangst     — økt uten spor forsvinner ikke, den havner synlig
  3. synlighet          — flaten får vite at oppryddingen gjenstår

🔑 Testene bruker DEFAULTS og skitne verdier, ikke pene tall. En test som ikke
speiler ekte datamønstre beviser ingenting — den gir falsk trygghet.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", 'fiq')
class TestSporNormalisering(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Spor = cls.env["fiq.ai.spor"]
        cls.Okt = cls.env["fiq.ai.okt"]

    # ── 1. KODENORMALISERING ────────────────────────────────────────────────
    def test_alias_gir_samme_kanoniske_kode(self):
        """«gui kr», «Kontrollrom» og «KR» er samme arbeid — ett spor, ikke tre."""
        for variant in ("KR", "kr", "gui kr", "GUI KR", "Kontrollrom", "kontrollrom"):
            self.assertEqual(
                self.Spor.normaliser_kode(variant), "KR",
                "«%s» skulle blitt kanonisk «KR» — ellers får vi spor-drift." % variant,
            )

    def test_alias_dekker_de_levende_sporene(self):
        """Aliasene skal treffe sporene som faktisk finnes i dag, ikke oppdiktede."""
        self.assertEqual(self.Spor.normaliser_kode("Meldingssenteret"), "KOMM")
        self.assertEqual(self.Spor.normaliser_kode("prosjektoversikt"), "PRJ")
        self.assertEqual(self.Spor.normaliser_kode("Regnskap"), "FIN")
        self.assertEqual(self.Spor.normaliser_kode("airmm"), "AI KR")

    def test_ukjent_kode_ryddes_men_finnes_ikke_opp(self):
        """En kode vi ikke kjenner skal ryddes — aldri gjettes om til noe annet."""
        self.assertEqual(self.Spor.normaliser_kode("  befaring  "), "BEFARING")
        self.assertEqual(self.Spor.normaliser_kode("ny   ting"), "NY TING")

    def test_tom_kode_gir_tom_streng(self):
        for tom in ("", "   ", False, None):
            self.assertEqual(self.Spor.normaliser_kode(tom), "")

    def test_finn_eller_lag_gjenbruker_i_stedet_for_a_duplisere(self):
        """To ulike skrivemåter skal lande i ETT spor — det er hele poenget."""
        forste = self.Spor._finn_eller_lag("gui kr")
        andre = self.Spor._finn_eller_lag("Kontrollrom")
        self.assertTrue(forste)
        self.assertEqual(forste, andre,
                         "To skrivemåter av samme spor ga to poster — kaoset flyttet seg.")

    # ── 2. HJEMLØS-FANGST ───────────────────────────────────────────────────
    def test_okt_uten_spor_havner_i_uten_spor(self):
        """MYKT krav: økta avvises ikke, men den blir heller ikke usynlig."""
        okt_id = self.Okt.registrer_okt(name="Testøkt uten tilhørighet")
        okt = self.Okt.browse(okt_id)
        self.assertTrue(okt.spor_id, "Økta ble hjemløs — nøyaktig feilen vi retter.")
        self.assertEqual(okt.spor_id.kode, self.Spor.HJEMLOS_KODE)

    def test_okt_med_spor_havner_ikke_i_uten_spor(self):
        okt_id = self.Okt.registrer_okt(name="Testøkt med spor", spor_kode="AI KR")
        self.assertEqual(self.Okt.browse(okt_id).spor_id.kode, "AI KR")

    def test_eksisterende_spor_overskrives_ikke_ved_oppdatering(self):
        """En økt som alt HAR spor skal ikke miste det når den melder fremdrift.

        Dette er den farlige varianten: økta rapporterer status uten å gjenta
        sporkoden, og ville — med naiv kode — blitt dyttet til «Uten spor».
        """
        ref = "test-ref-beholder-spor"
        self.Okt.registrer_okt(name="Økt A", okt_ref=ref, spor_kode="PRJ")
        okt_id = self.Okt.registrer_okt(name="Økt A", okt_ref=ref, status="pause")
        self.assertEqual(self.Okt.browse(okt_id).spor_id.kode, "PRJ",
                         "Sporet gikk tapt ved en ren statusoppdatering.")

    def test_hjemlost_spor_gjenbrukes(self):
        """Oppsamlingssporet skal finnes i ÉN utgave, uansett hvor mange som treffer det."""
        self.Okt.registrer_okt(name="Hjemløs 1")
        self.Okt.registrer_okt(name="Hjemløs 2")
        treff = self.Spor.search([("kode", "=", self.Spor.HJEMLOS_KODE)])
        self.assertEqual(len(treff), 1,
                         "Flere «Uten spor»-poster — da er oversikten verdiløs.")

    # ── 3. SYNLIGHET I FLATEN ───────────────────────────────────────────────
    def test_flaten_flagger_at_opprydding_gjenstar(self):
        """Hjemløse økter må SYNES. Usynlighet lot 3 moduler stå eierløse i 11 dager."""
        self.Okt.registrer_okt(name="Hjemløs som skal synes")
        rader = self.env["fiq.gui.ai.kr.data"].get_spor()
        hjemlose = [r for r in rader if r.get("hjemlost")]
        self.assertEqual(len(hjemlose), 1, "Oppsamlingssporet vises ikke i flaten.")
        self.assertTrue(hjemlose[0]["krever_opprydding"],
                        "Sporet har økter, men flaten sier ikke fra.")

    def test_vanlig_spor_er_ikke_flagget(self):
        """Flagget skal treffe oppsamlingssporet — ikke ekte spor."""
        self.Spor._finn_eller_lag("AI KR")
        rader = self.env["fiq.gui.ai.kr.data"].get_spor()
        vanlige = [r for r in rader if r["kode"] == "AI KR"]
        self.assertTrue(vanlige, "Sporet «AI KR» kom ikke med i flaten.")
        self.assertFalse(vanlige[0]["hjemlost"])
        self.assertFalse(vanlige[0]["krever_opprydding"])
