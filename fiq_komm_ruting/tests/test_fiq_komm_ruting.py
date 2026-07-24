#
# Tester for e-post-ruting: postkasse → firma.
#
# Modulen hadde NULL tester (84 linjer, 4 py-filer) og ble stoppet av CI-gaten.
#
# Hva som testes, og hvorfor akkurat dette:
# `finn_firma()` er AUTORITATIV for hvilket firma innkommende post havner i. Treffer den
# feil, havner en kundes e-post i en annen kundes base — tenant-lekkasje, den alvorligste
# feilen vi kan lage ([[fiq-vokter]]). Derfor tester vi ikke bare at metoden svarer, men
# at den svarer RIKTIG på hele domenet den filtrerer på:
#     ("mailbox", "=ilike", …)  +  ("aktiv", "=", True)
#
# 🛑 PORT 6: testdataen må oppfylle HELE domenet, ikke bare eksistere. En profil uten
# `aktiv=False`-motstykke beviser ikke at aktiv-filteret virker — den beviser bare at
# oppslaget finner noe.

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


# Taggene: `post_install` fordi andre moduler legger NOT NULL-kolonner på
# res.company/res.users under installasjon — under `at_install` er de feltene ukjente
# for registryet.
# `fiq`-taggen står igjen fra da CI filtrerte på den. Gaten filtrerer nå på MODULNAVN
# (`--test-tags=/fiq_komm_ruting`, verifisert i odoo/tests/tag_selector.py:20), som tar
# ALLE tester i modulen uansett tagg. Taggen skader ikke og beholdes — men den er ikke
# lenger det som avgjør om testene kjøres.
@tagged("post_install", "-at_install", "fiq")
class TestKommRuting(TransactionCase):
    def setUp(self):
        super().setUp()
        self.Profil = self.env["fiq.komm.profil"]
        # Egen tilstand (port 6) — vi leser aldri data noen andre har lagt inn.
        self.firma_a = self.env["res.company"].create({"name": "TEST Ruting Firma A"})
        self.firma_b = self.env["res.company"].create({"name": "TEST Ruting Firma B"})

    # ---- Kjernen: riktig firma ----------------------------------------------------

    def test_finner_riktig_firma(self):
        """Grunnfunksjonen: en kjent postkasse skal gi SITT firma."""
        self.Profil.create(
            {
                "mailbox": "post@testruting-a.no",
                "company_id": self.firma_a.id,
                "er_felles": True,
                "backend": "m365",
            }
        )
        r = self.Profil.finn_firma("post@testruting-a.no")
        self.assertEqual(r.get("company_id"), self.firma_a.id)
        self.assertTrue(r.get("er_felles"))
        self.assertEqual(r.get("backend"), "m365")

    def test_to_firmaer_blandes_ALDRI(self):
        """🛑 TENANT-ISOLASJON: to postkasser, to firmaer. Treffer oppslaget feil,
        havner én kundes e-post i en annen kundes base. Dette er den alvorligste
        feilen modulen kan gjøre, og derfor den viktigste testen her."""
        self.Profil.create(
            {"mailbox": "post@firma-a.no", "company_id": self.firma_a.id}
        )
        self.Profil.create(
            {"mailbox": "post@firma-b.no", "company_id": self.firma_b.id}
        )
        self.assertEqual(
            self.Profil.finn_firma("post@firma-a.no")["company_id"], self.firma_a.id
        )
        self.assertEqual(
            self.Profil.finn_firma("post@firma-b.no")["company_id"], self.firma_b.id
        )

    # ---- HELE domenet: aktiv-filteret ---------------------------------------------

    def test_inaktiv_profil_ignoreres(self):
        """Domenet filtrerer på `aktiv = True`. En deaktivert profil skal IKKE treffe —
        ellers ville post fortsatt rutet til et firma man bevisst har koblet fra.
        (Port 6: testdataen dekker BEGGE sider av filteret, ikke bare den som treffer.)"""
        self.Profil.create(
            {
                "mailbox": "gammel@testruting.no",
                "company_id": self.firma_a.id,
                "aktiv": False,
            }
        )
        self.assertEqual(
            self.Profil.finn_firma("gammel@testruting.no"),
            {},
            "inaktiv profil skal gi tomt svar, ikke firma",
        )

    def test_aktiv_vinner_over_inaktiv_paa_samme_adresse(self):
        """Samme adresse kan finnes både aktiv og inaktiv (etter en flytting).
        Da skal den AKTIVE svare — ellers ruter vi etter historikk i stedet for nåtid."""
        self.Profil.create(
            {
                "mailbox": "flyttet@testruting.no",
                "company_id": self.firma_a.id,
                "aktiv": False,
            }
        )
        self.Profil.create(
            {
                "mailbox": "flyttet@testruting.no",
                "company_id": self.firma_b.id,
                "aktiv": True,
            }
        )
        self.assertEqual(
            self.Profil.finn_firma("flyttet@testruting.no")["company_id"],
            self.firma_b.id,
        )

    # ---- HELE domenet: `=ilike` og inndata ----------------------------------------

    def test_store_bokstaver_og_mellomrom_treffer(self):
        """Domenet bruker `=ilike` + `.strip()`. E-postadresser kommer fra eksterne
        systemer med vilkårlig store bokstaver og mellomrom rundt — treffer vi ikke da,
        faller posten til manuell håndtering uten at noen skjønner hvorfor."""
        self.Profil.create(
            {"mailbox": "Post@TestRuting.no", "company_id": self.firma_a.id}
        )
        for variant in (
            "post@testruting.no",
            "POST@TESTRUTING.NO",
            "  Post@TestRuting.no  ",
        ):
            self.assertEqual(
                self.Profil.finn_firma(variant).get("company_id"),
                self.firma_a.id,
                f"traff ikke på: {variant!r}",
            )

    def test_ukjent_og_tom_gir_tomt_svar_ikke_krasj(self):
        """Ukjent adresse skal falle tilbake på manuell ruting — ikke kaste.
        En exception her ville stoppet HELE innhentingen av post."""
        self.assertEqual(self.Profil.finn_firma("finnes-ikke@ingensteds.no"), {})
        self.assertEqual(self.Profil.finn_firma(""), {})
        self.assertEqual(self.Profil.finn_firma(False), {})

    # ---- Eierskap: GDPR-siden ------------------------------------------------------

    def test_personlig_postkasse_baerer_eieren(self):
        """Personlig postkasse = eierens. `owner_user_id` må følge med ut, ellers kan
        ikke flaten skjule personlig post for andre enn eieren (GDPR, per-bruker-samtykke)."""
        p = self.Profil.create(
            {
                "mailbox": "privat@testruting.no",
                "company_id": self.firma_a.id,
                "owner_user_id": self.env.user.id,
                "er_felles": False,
            }
        )
        r = self.Profil.finn_firma("privat@testruting.no")
        self.assertEqual(r["owner_user_id"], self.env.user.id)
        self.assertFalse(r["er_felles"])
        self.assertTrue(p.exists())

    def test_felles_postkasse_har_ingen_eier(self):
        """Felles postkasse (post@/faktura@) eies av firmaet — trygt å lese sentralt.
        `owner_user_id` skal da være False, ikke en tilfeldig bruker."""
        self.Profil.create(
            {
                "mailbox": "faktura@testruting.no",
                "company_id": self.firma_a.id,
                "er_felles": True,
            }
        )
        r = self.Profil.finn_firma("faktura@testruting.no")
        self.assertFalse(r["owner_user_id"])
        self.assertTrue(r["er_felles"])

    # ---- Databaseskranken ----------------------------------------------------------

    def test_samme_postkasse_kan_betjene_to_firmaer(self):
        """Skranken er `unique(mailbox, company_id)` — ikke `unique(mailbox)`.
        Samme adresse KAN finnes i to firmaer (f.eks. en delt leverandøradresse),
        men ikke to ganger i samme firma."""
        self.Profil.create(
            {"mailbox": "delt@testruting.no", "company_id": self.firma_a.id}
        )
        p2 = self.Profil.create(
            {"mailbox": "delt@testruting.no", "company_id": self.firma_b.id}
        )
        self.assertTrue(p2.exists(), "samme adresse i to ULIKE firmaer skal være lov")
