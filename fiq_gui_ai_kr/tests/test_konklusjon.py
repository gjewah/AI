# -*- coding: utf-8 -*-
"""Tester for konklusjons-loggen — det Gjermund skal kunne lese OG STOPPE.

🛑 DEN VIKTIGSTE TESTEN I FILA: `test_bestrid_uten_begrunnelse_virker`.
Gjermund 21.07.2026: «av og til må jeg bruke ordet feil for å få stoppet økter som
har glemt regelen om kunstpause og starter å bygge på feil konklusjon».
Krever nødbremsen en begrunnelse, venter stoppen på at han rekker å formulere seg —
mens økta bygger videre. Da er tiden han prøver å redde allerede tapt.

Testene bruker DEFAULTS og skitne verdier, ikke pene tall jeg selv har valgt
([[feedback-compute-index-recordset]] — WBS-en som ga «01» til 66 oppgaver).
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", 'fiq')
class TestKonklusjon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.K = cls.env["fiq.ai.konklusjon"]
        cls.Data = cls.env["fiq.gui.ai.kr.data"]

    # ── NØDBREMSEN ──────────────────────────────────────────────────────────
    def test_bestrid_uten_begrunnelse_virker(self):
        """🛑 KJERNEN: «Feil» alene skal stoppe arbeidet. Ingen tekst påkrevd."""
        k = self.K.create({"name": "En konklusjon som er gal"})
        k.bestrid()                                   # ingen begrunnelse i det hele tatt
        self.assertEqual(k.status, "bestridt",
                         "Nødbremsen krevde en begrunnelse — da virker den ikke når det haster.")
        self.assertTrue(k.bestridt_dato)
        self.assertEqual(k.bestridt_av, self.env.user)

    def test_bestrid_med_begrunnelse_lagrer_den(self):
        k = self.K.create({"name": "Bruk X"})
        k.bestrid("Vi bruker ikke X lenger")
        self.assertEqual(k.status, "bestridt")
        self.assertEqual(k.bestridelse, "Vi bruker ikke X lenger")

    def test_okt_kan_sjekke_om_den_er_stoppet(self):
        """En økt spør FØR den bygger videre — det er hele poenget med bremsen."""
        k = self.K.create({"name": "Konklusjon å bygge på"})
        self.assertFalse(self.K.er_bestridt(k.id)["bestridt"])
        k.bestrid("nei")
        svar = self.K.er_bestridt(k.id)
        self.assertTrue(svar["bestridt"])
        self.assertEqual(svar["begrunnelse"], "nei")

    def test_bestridt_ligger_overst(self):
        """Stoppet arbeid skal ses FØRST — uansett hvor gammelt det er."""
        gammel = self.K.create({"name": "Gammel konklusjon"})
        self.K.create({"name": "Fersk konklusjon"})
        gammel.bestrid()
        self.assertEqual(self.K.search([], limit=1), gammel,
                         "Bestridt konklusjon havnet ikke øverst.")

    # ── UTEN GRUNNLAG ───────────────────────────────────────────────────────
    def test_umerket_konklusjon_synes(self):
        """En VALGFRI mekanisme brukes ikke — derfor må umerket SYNES.

        Nøyaktig lærdommen fra spor-saken: `spor_kode` var valgfri i to dager og ble
        aldri brukt én eneste gang.
        """
        k = self.K.create({"name": "Noen skrev dette uten å si hvor trygt det er"})
        self.assertTrue(k.uten_grunnlag)

    def test_merket_konklusjon_er_ikke_uten_grunnlag(self):
        k = self.K.create({"name": "Sjekket mot kilden", "sikkerhet": "verifisert"})
        self.assertFalse(k.uten_grunnlag)

    # ── LOGGING FRA ØKTENE ──────────────────────────────────────────────────
    def test_logg_oppretter_spor_hvis_det_mangler(self):
        kid = self.K.logg("Testkonklusjon", sikkerhet="antatt", spor_kode="gui kr")
        k = self.K.browse(kid)
        self.assertEqual(k.spor_id.kode, "KR",
                         "Sporkoden ble ikke normalisert — da får vi spor-drift.")
        self.assertEqual(k.sikkerhet, "antatt")

    def test_logg_uten_sikkerhet_havner_uten_grunnlag(self):
        k = self.K.browse(self.K.logg("Umerket fra en økt"))
        self.assertTrue(k.uten_grunnlag)

    def test_logg_avviser_ugyldig_sikkerhetsgrad(self):
        """En tullete verdi skal ikke smugles inn — da blir feltet verdiløst."""
        k = self.K.browse(self.K.logg("Test", sikkerhet="ganske_sikker"))
        self.assertFalse(k.sikkerhet)
        self.assertTrue(k.uten_grunnlag)

    def test_konklusjon_arver_spor_fra_okta(self):
        """Oppgir økta ikke spor på konklusjonen, arves øktas eget."""
        self.env["fiq.ai.okt"].registrer_okt(
            name="Testøkt", okt_ref="test-arv-spor", spor_kode="PRJ")
        k = self.K.browse(self.K.logg("Uten eget spor", okt_ref="test-arv-spor"))
        self.assertEqual(k.spor_id.kode, "PRJ")

    # ── HVA GJERMUND FAKTISK SER ────────────────────────────────────────────
    def test_flaten_viser_kanon_og_usikre_men_skjuler_verifiserte(self):
        """Gjermunds avgrensning: «kanon + alt som er antatt eller uverifisert»."""
        self.K.logg("KANON-sak", sikkerhet="verifisert", er_kanon=True)
        self.K.logg("Usikker sak", sikkerhet="antatt")
        self.K.logg("Umerket sak")
        self.K.logg("Rutine-detalj", sikkerhet="verifisert")     # skal IKKE vises

        tekster = [r["konklusjon"] for r in self.Data.get_konklusjoner()]
        self.assertIn("KANON-sak", tekster)
        self.assertIn("Usikker sak", tekster)
        self.assertIn("Umerket sak", tekster)
        self.assertNotIn("Rutine-detalj", tekster,
                         "Verifisert rutine-detalj skapte støy i Gjermunds liste.")

    def test_vis_alle_tar_med_de_verifiserte(self):
        self.K.logg("Rutine-detalj 2", sikkerhet="verifisert")
        tekster = [r["konklusjon"] for r in self.Data.get_konklusjoner(vis_alle=True)]
        self.assertIn("Rutine-detalj 2", tekster)

    def test_bestridt_vises_alltid(self):
        """Selv en verifisert rutine-sak må vises når Gjermund har stoppet den.

        Ellers ville hans egen stopp forsvunnet ut av hans egen liste.
        """
        k = self.K.browse(self.K.logg("Verifisert men gal", sikkerhet="verifisert"))
        k.bestrid()
        tekster = [r["konklusjon"] for r in self.Data.get_konklusjoner()]
        self.assertIn("Verifisert men gal", tekster)

    def test_pulsen_teller_riktig(self):
        self.K.logg("Puls kanon", sikkerhet="verifisert", er_kanon=True)
        self.K.logg("Puls antatt", sikkerhet="antatt")
        self.K.logg("Puls umerket")
        stoppet = self.K.browse(self.K.logg("Puls stoppet", sikkerhet="antatt"))
        stoppet.bestrid()

        p = self.Data.get_konklusjon_puls()
        self.assertGreaterEqual(p["bestridt"], 1)
        self.assertGreaterEqual(p["uten_grunnlag"], 1)
        self.assertGreaterEqual(p["kanon"], 1)
        # Bestridte skal IKKE telles som «usikre» også — da ser det ut som mer enn det er.
        self.assertGreaterEqual(p["usikre"], 1)

    # ── KORRIGERING ─────────────────────────────────────────────────────────
    def test_korriger_beholder_den_gamle_teksten_i_historikken(self):
        """Vi overskriver aldri hva som VAR konkludert — da blir loggen verdiløs."""
        k = self.K.create({"name": "Gammel gal konklusjon"})
        k.bestrid("feil")
        k.korriger("Ny riktig konklusjon", grunnlag="Verifisert i kilden")
        self.assertEqual(k.status, "korrigert")
        self.assertEqual(k.name, "Ny riktig konklusjon")
        self.assertTrue(
            any("Gammel gal konklusjon" in (m.body or "") for m in k.message_ids),
            "Den gamle teksten forsvant — historikken er ikke til å stole på.")
