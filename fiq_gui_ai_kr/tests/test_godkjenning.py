# -*- coding: utf-8 -*-
"""Tester for godkjenningskøen — det som fjerner klikkingen fra Gjermunds hverdag.

Gjermund 22.07.2026: «Jeg rekker knapt gjøre annet enn å prøve å holde progresjon
ved å trykke ALLOW hvert tredje til hvert femte sekund.»

🔑 VIKTIGSTE TEST: `test_alltid_svarer_neste_sporsmaal_selv`.
«Alltid» er hele svaret på sitatet over. Virker den ikke, kommer samme spørsmål
tilbake i det uendelige — og knappen er en løgn.
"""

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestGodkjenning(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.G = cls.env["fiq.ai.godkjenning"]
        cls.Data = cls.env["fiq.gui.ai.kr.data"]

    def tearDown(self):
        # Stående regler lagres i ir.config_parameter og overlever IKKE rollback
        # på samme måte som poster. Rydder eksplisitt så tester ikke smitter.
        for r in self.G.staaende_regler():
            self.G.trekk_tilbake(r["noekkel"])
        super().tearDown()

    # ── «ALLTID» — KJERNEN ──────────────────────────────────────────────────
    def test_alltid_svarer_neste_sporsmaal_selv(self):
        """🔑 Gjermund svarer ÉN gang. Neste gang svarer systemet."""
        f = self.G.spor("Push til grenen?", noekkel="push_gren")
        self.assertIsNone(f["svar"], "Første spørsmål skal ikke være besvart.")
        self.G.browse(f["id"]).svar_paa("alltid")

        andre = self.G.spor("Push til grenen igjen?", noekkel="push_gren")
        self.assertEqual(andre["svar"], "godkjent",
                         "«Alltid» virket ikke — spørsmålet kom tilbake til Gjermund.")
        self.assertTrue(andre["staaende"])
        self.assertFalse(andre["id"], "Det ble laget en kø-rad likevel — da er den ikke stille.")

    def test_alltid_gjelder_kun_samme_noekkel(self):
        """Et ja på én ting er ikke et ja på alt."""
        self.G.browse(self.G.spor("A?", noekkel="ting_a")["id"]).svar_paa("alltid")
        annen = self.G.spor("B?", noekkel="ting_b")
        self.assertIsNone(annen["svar"], "«Alltid» lekket over til et annet spørsmål.")

    def test_alltid_uten_noekkel_lagrer_ingen_regel(self):
        """Uten nøkkel kan ingenting gjenkjennes — da skal heller ingenting lagres.

        Alternativet ville vært en stående regel som aldri treffer: en knapp som
        later som den husker.
        """
        self.G.browse(self.G.spor("Noe uten nøkkel?")["id"]).svar_paa("alltid")
        self.assertEqual(self.G.staaende_regler(), [])

    def test_trekk_tilbake_gjor_at_systemet_spor_igjen(self):
        """En regel Gjermund ikke kan angre, er en regel han ikke kontrollerer."""
        self.G.browse(self.G.spor("Push?", noekkel="angre_meg")["id"]).svar_paa("alltid")
        self.assertEqual(self.G.spor("Push?", noekkel="angre_meg")["svar"], "godkjent")

        self.assertTrue(self.G.trekk_tilbake("angre_meg"))
        self.assertIsNone(self.G.spor("Push?", noekkel="angre_meg")["svar"],
                          "Regelen ble trukket tilbake, men systemet svarer fortsatt selv.")

    def test_staaende_regler_kan_listes(self):
        self.G.browse(self.G.spor("X?", noekkel="synlig_regel")["id"]).svar_paa("alltid")
        self.assertIn("synlig_regel", [r["noekkel"] for r in self.G.staaende_regler()])

    # ── «JA, MEN…» ──────────────────────────────────────────────────────────
    def test_ja_men_krever_forbehold(self):
        """Et forbehold ingen kan lese er ikke et forbehold.

        Uten denne sperren ville økta fått «ja» og fortsatt som om intet var sagt.
        """
        g = self.G.browse(self.G.spor("Med forbehold?")["id"])
        with self.assertRaises(UserError):
            g.svar_paa("ja_men")
        with self.assertRaises(UserError):
            g.svar_paa("ja_men", "   ")          # bare mellomrom teller ikke

    def test_ja_men_med_forbehold_lagres(self):
        g = self.G.browse(self.G.spor("Med forbehold?")["id"])
        g.svar_paa("ja_men", "Kun add-only, ingen slettinger")
        self.assertEqual(g.svar, "ja_men")
        self.assertEqual(g.forbehold, "Kun add-only, ingen slettinger")

    def test_okta_ser_forbeholdet(self):
        """Økta må kunne LESE forbeholdet — ellers er sperren over meningsløs."""
        g = self.G.browse(self.G.spor("Sjekk?")["id"])
        g.svar_paa("ja_men", "Vent til etter kl. 16")
        svar = self.G.hent_svar(g.id)
        self.assertEqual(svar["svar"], "ja_men")
        self.assertEqual(svar["forbehold"], "Vent til etter kl. 16")

    # ── KØEN GJERMUND SER ───────────────────────────────────────────────────
    def test_ubesvarte_ligger_overst(self):
        besvart = self.G.browse(self.G.spor("Alt besvart")["id"])
        besvart.svar_paa("godkjent")
        self.G.spor("Venter fortsatt")
        self.assertFalse(self.G.search([], limit=1).svar,
                         "Et besvart spørsmål lå øverst — da drukner det ubesvarte.")

    def test_koen_viser_kun_ubesvarte_som_default(self):
        self.G.browse(self.G.spor("Ferdig sak")["id"]).svar_paa("nei")
        self.G.spor("Åpen sak")
        tekster = [r["sporsmaal"] for r in self.Data.get_godkjenninger()]
        self.assertIn("Åpen sak", tekster)
        self.assertNotIn("Ferdig sak", tekster)

    def test_riktig_knapperad_per_art(self):
        """Fasiten har TO knapperader. Feil rad = feil spørsmål til Gjermund."""
        self.G.spor("Vanlig godkjenning?", art="godkjenning")
        self.G.spor("Skaff Admin-nøkkel?", art="oppgave", kilde="klokke")
        rader = {r["sporsmaal"]: r for r in self.Data.get_godkjenninger()}

        gk = [k["valg"] for k in rader["Vanlig godkjenning?"]["knapper"]]
        self.assertEqual(gk, ["godkjent", "ja_men", "nei", "alltid"])

        op = [k["valg"] for k in rader["Skaff Admin-nøkkel?"]["knapper"]]
        self.assertEqual(op, ["jeg_gjor", "senere", "dropp"])
        self.assertEqual(rader["Skaff Admin-nøkkel?"]["kilde_tekst"], "👤 Klokke-oppgave")

    def test_kan_alltid_er_ærlig(self):
        """«Alltid»-knappen skal bare loves der den faktisk kan huske noe."""
        self.G.spor("Med nøkkel?", noekkel="har_noekkel")
        self.G.spor("Uten nøkkel?")
        rader = {r["sporsmaal"]: r for r in self.Data.get_godkjenninger()}
        self.assertTrue(rader["Med nøkkel?"]["kan_alltid"])
        self.assertFalse(rader["Uten nøkkel?"]["kan_alltid"])

    def test_svar_via_datalaget(self):
        f = self.G.spor("Via flaten?")
        r = self.Data.svar_godkjenning(f["id"], "godkjent")
        self.assertTrue(r["ok"])
        self.assertEqual(self.G.browse(f["id"]).svar, "godkjent")

    def test_ukjent_svar_avvises(self):
        g = self.G.browse(self.G.spor("Test?")["id"])
        with self.assertRaises(UserError):
            g.svar_paa("kanskje")

    # ── FORANKRING ──────────────────────────────────────────────────────────
    def test_sporsmaal_arver_spor_fra_okta(self):
        """Sporet eier spørsmålet — økta som spurte er borte om to dager."""
        self.env["fiq.ai.okt"].registrer_okt(
            name="Spørrende økt", okt_ref="gk-arv-test", spor_kode="AI KR")
        g = self.G.browse(self.G.spor("Arver spor?", okt_ref="gk-arv-test")["id"])
        self.assertEqual(g.spor_id.kode, "AI KR")

    def test_eget_spor_vinner_over_oktas(self):
        self.env["fiq.ai.okt"].registrer_okt(
            name="Økt 2", okt_ref="gk-eget-spor", spor_kode="AI KR")
        g = self.G.browse(self.G.spor(
            "Eget spor?", okt_ref="gk-eget-spor", spor_kode="PRJ")["id"])
        self.assertEqual(g.spor_id.kode, "PRJ")
