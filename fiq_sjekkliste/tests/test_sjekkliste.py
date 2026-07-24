"""Tester for den generiske sjekkliste-motoren (fiq.sjekkliste + .punkt).

Hvorfor disse testene finnes (GUI Prosjekt V0.02, 2026-07-18):
Modulen hadde 0 tester — `--test-enable` ga «0 failed, 0 error(s) of 0 tests».
Den «bestod» fordi det ikke fantes noe å teste = falsk trygghet. Sjekkliste-motoren
håndhever Gjermunds krav-regler (dok/foto/signatur, uavhengige) og ISO 9001-versjonering;
begge deler er forretningsregler som MÅ være bevist, ikke antatt.

Testene speiler reglene slik de er kanonisert:
  * «Det er kun avvik og endringer som er bilder og/eller dokumenter.»
  * FDV og klima ER dokumenter, ikke bilder.
  * Et punkt kan ikke kvitteres ut før ALLE krav er levert.
  * ISO 9001: enhver endring bumper listas versjon (kan rulles tilbake).
"""

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_sjekkliste", "fiq")
class TestFiqSjekkliste(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # NB: project.project.create() kan feile på required+compute+store-felt
        # (jf. billing_type-funnet i fiq_gui_control 17.07). Vi lager derfor
        # sjekklister uten prosjekt der testen ikke trenger et.
        cls.Sjekkliste = cls.env["fiq.sjekkliste"]
        cls.Punkt = cls.env["fiq.sjekkliste.punkt"]

    def _lag_liste(self, **vals):
        return self.Sjekkliste.create(dict({"name": "Testliste"}, **vals))

    # ---------- FREMDRIFT ----------

    def test_fremdrift_tom_liste_er_null(self):
        """Tom liste skal gi 0 %, ikke divisjon på null."""
        liste = self._lag_liste()
        self.assertEqual(liste.antall_punkt, 0)
        self.assertEqual(liste.antall_ok, 0)
        self.assertEqual(liste.fremdrift, 0.0)

    def test_fremdrift_regnes_riktig(self):
        """2 av 4 utført = 50 %."""
        liste = self._lag_liste()
        for i in range(4):
            self.Punkt.create({"sjekkliste_id": liste.id, "name": f"P{i}"})
        liste.punkt_ids[:2].write({"utfoert": True})
        self.assertEqual(liste.antall_punkt, 4)
        self.assertEqual(liste.antall_ok, 2)
        self.assertAlmostEqual(liste.fremdrift, 50.0, places=2)

    # ---------- KRAV-REGLENE (Gjermunds kjerneregel) ----------

    def test_punkt_uten_krav_kan_kvitteres_direkte(self):
        """Ingen krav satt -> punktet kan kvitteres uten vedlegg."""
        liste = self._lag_liste()
        p = self.Punkt.create({"sjekkliste_id": liste.id, "name": "Fri"})
        self.assertTrue(p.kan_kvitteres)
        self.assertFalse(p.mangler)
        p.utfoert = True  # skal ikke kaste
        self.assertTrue(p.utfoert)

    def test_krav_dokument_blokkerer_til_dokument_er_lagt_ved(self):
        """FDV/klima = DOKUMENT. Kan ikke kvitteres før dokumentet finnes."""
        liste = self._lag_liste(type_liste="fdv")
        p = self.Punkt.create(
            {
                "sjekkliste_id": liste.id,
                "name": "FDV-perm",
                "krav_dok": True,
            }
        )
        self.assertFalse(p.kan_kvitteres)
        self.assertEqual(p.mangler, "dokument")
        with self.assertRaises(ValidationError):
            p.utfoert = True

        vedlegg = self.env["ir.attachment"].create({"name": "fdv.pdf"})
        p.kvitt_dok_id = vedlegg
        self.assertTrue(p.kan_kvitteres)
        p.utfoert = True
        self.assertTrue(p.utfoert)

    def test_krav_er_uavhengige_og_kombinerbare(self):
        """«bilder OG/ELLER dokumenter» — kravene er uavhengige, ikke enten/eller.

        Avvik er nettopp tilfellet der begge kan gjelde samtidig.
        """
        liste = self._lag_liste(type_liste="avvik")
        p = self.Punkt.create(
            {
                "sjekkliste_id": liste.id,
                "name": "Avvik tak",
                "krav_dok": True,
                "krav_foto": True,
                "krav_sign": True,
            }
        )
        # Alle tre mangler -> alle tre nevnes
        self.assertFalse(p.kan_kvitteres)
        for ord_ in ("dokument", "foto", "signatur"):
            self.assertIn(ord_, p.mangler)

        att = self.env["ir.attachment"]
        p.kvitt_dok_id = att.create({"name": "rapport.pdf"})
        self.assertFalse(p.kan_kvitteres)  # foto + signatur igjen
        p.kvitt_foto_id = att.create({"name": "tak.jpg"})
        self.assertFalse(p.kan_kvitteres)  # signatur igjen
        self.assertEqual(p.mangler, "signatur")

        p.kvitt_sign_dato = "2026-07-18 10:00:00"
        self.assertTrue(p.kan_kvitteres)
        p.utfoert = True

    def test_signatur_alene_er_nok_naar_bare_signatur_kreves(self):
        """Overlevering: kun signatur kreves — dokument skal ikke kreves implisitt."""
        liste = self._lag_liste(type_liste="arbeid")
        p = self.Punkt.create(
            {
                "sjekkliste_id": liste.id,
                "name": "Overlevert",
                "krav_sign": True,
            }
        )
        self.assertEqual(p.mangler, "signatur")
        p.kvitt_sign_dato = "2026-07-18 10:00:00"
        self.assertTrue(p.kan_kvitteres)
        p.utfoert = True
        self.assertTrue(p.utfoert)

    def test_kan_ikke_omgaa_krav_ved_aa_sette_utfoert_i_create(self):
        """Regelen må også holde ved create() — ikke bare ved write()."""
        liste = self._lag_liste()
        with self.assertRaises(ValidationError):
            self.Punkt.create(
                {
                    "sjekkliste_id": liste.id,
                    "name": "Snarvei",
                    "krav_dok": True,
                    "utfoert": True,
                }
            )

    def test_fjernet_kvittering_gjenaapner_kravet(self):
        """Fjernes dokumentet, skal punktet ikke lenger regnes som kvitterbart."""
        liste = self._lag_liste()
        att = self.env["ir.attachment"].create({"name": "d.pdf"})
        p = self.Punkt.create(
            {
                "sjekkliste_id": liste.id,
                "name": "P",
                "krav_dok": True,
                "kvitt_dok_id": att.id,
            }
        )
        self.assertTrue(p.kan_kvitteres)
        p.kvitt_dok_id = False
        self.assertFalse(p.kan_kvitteres)
        self.assertEqual(p.mangler, "dokument")

    # ---------- ISO 9001-VERSJONERING ----------

    def test_versjon_bumpes_ved_endring(self):
        """ISO 9001: enhver endring på et punkt bumper listas versjon."""
        liste = self._lag_liste()
        self.assertEqual(liste.versjon, "1.0")
        p = self.Punkt.create({"sjekkliste_id": liste.id, "name": "P"})
        p.write({"name": "P endret"})
        self.assertEqual(liste.versjon, "1.1")
        p.write({"beskrivelse": "mer"})
        self.assertEqual(liste.versjon, "1.2")

    def test_versjon_bumpes_ikke_av_irrelevant_felt(self):
        """Rekkefølge-endring er ikke en innholdsendring -> ingen versjonsbump."""
        liste = self._lag_liste()
        p = self.Punkt.create({"sjekkliste_id": liste.id, "name": "P"})
        versjon_for = liste.versjon
        p.write({"sequence": 99})
        self.assertEqual(liste.versjon, versjon_for)

    def test_versjon_taaler_ugyldig_verdi(self):
        """Er versjonsfeltet korrupt, skal motoren falle tilbake til 1.0 — ikke kaste."""
        liste = self._lag_liste()
        liste.sudo().write({"versjon": "tull"})
        liste._bump_versjon()
        self.assertEqual(liste.versjon, "1.0")

    # ---------- TENANT-ISOLASJON ----------

    def test_firma_settes_fra_sesjonen(self):
        """Scope hentes fra sesjonen — aldri fra klient (kanon: tenant-isolasjon)."""
        liste = self._lag_liste()
        self.assertEqual(liste.company_id, self.env.company)
