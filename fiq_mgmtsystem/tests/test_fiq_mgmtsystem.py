"""Tester for FIQ Styringssystem (ISO 9001) — krav, kontroll, sjekkliste, avvik.

Hvorfor de finnes (2026-07-23): modulen hadde NULL tester. «0 failed, 0 error(s)
of 0 tests» leses som grønt, men beviser ingenting — det er falsk trygghet, samme
felle som fiq_gui_prj sto i 18.07. Modulen er FIQs ISO 9001-ryggrad: den svarer på
«etterlever vi standarden». Et galt tall her er ikke kosmetikk — det er en revisjon
som konkluderer feil.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand. En test som bare leser det
som tilfeldigvis ligger i basen kan ikke bevise fravær av data-betingede krasj. Alle
tall sammenlignes derfor som DIFFERANSE (før/etter) eller mot poster testen selv har
laget — aldri mot et absolutt tall som avhenger av demodata.

Tyngdepunktet er `_compute_fremdrift()`: den deler på antall punkter, og en
sjekkliste uten punkter er den normale tilstanden rett etter at noen har trykket
«ny sjekkliste». Nettopp null-tilfellene er det som mangler i testdekning.

post_install (ikke at_install): andre installerte moduler legger NOT NULL-kolonner
på res.users/res.partner som registryet ikke kjenner under at_install → NotNull-
Violation på felt denne modulen hverken eier eller ser. Samme grunn som
fiq_gui_relations/tests/test_fiq_gui_relation.py:6.
"""

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install", "fiq_mgmtsystem")
class TestFiqMgmtsystem(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Krav = cls.env["fiq.mgmtsystem.krav"]
        cls.Kontroll = cls.env["fiq.mgmtsystem.kontroll"]
        cls.Sjekkliste = cls.env["fiq.mgmtsystem.sjekkliste"]
        cls.Punkt = cls.env["fiq.mgmtsystem.sjekkliste.punkt"]
        cls.Avvik = cls.env["fiq.mgmtsystem.avvik"]
        # Unik suffiks: klausul er UNIK per (standard, company_id). Uten dette
        # kolliderer testene med hverandre og med data som alt ligger i basen.
        cls._teller = 0

    # ---------- byggeklosser (testen lager ALLTID sin egen tilstand) ----------

    @classmethod
    def _unik(cls):
        cls._teller += 1
        # 🛑 `:03d` MÅ bevares. Uten nullpolstringen blir T1/T2 i stedet for
        # T001/T002, og hele modulens unikhet hviler på denne ene strengen —
        # klausul, kode og login bygges av den.
        return f"T{cls._teller:03d}"

    def _lag_krav(self, **vals):
        """Ett krav med garantert unik klausul (unique(standard, klausul, company_id))."""
        u = self._unik()
        return self.Krav.create(
            dict(
                {
                    "name": f"Testkrav {u}",
                    "klausul": f"9.{u}",
                    "standard": "iso9001",
                },
                **vals,
            )
        )

    def _lag_kontroll(self, **vals):
        u = self._unik()
        return self.Kontroll.create(
            dict(
                {
                    "name": f"Testkontroll {u}",
                    "kode": f"K-{u}",
                },
                **vals,
            )
        )

    def _lag_liste(self, **vals):
        return self.Sjekkliste.create(
            dict(
                {
                    "name": f"Testsjekkliste {self._unik()}",
                },
                **vals,
            )
        )

    def _lag_punkter(self, liste, antall, utfort=False):
        """Oppretter N punkter på lista. Returnerer recordsettet."""
        return self.Punkt.create(
            [
                {
                    "sjekkliste_id": liste.id,
                    "name": f"Punkt {i + 1}",
                    "utfort": utfort,
                }
                for i in range(antall)
            ]
        )

    def _lag_avvik(self, **vals):
        return self.Avvik.create(
            dict(
                {
                    "name": f"Testavvik {self._unik()}",
                },
                **vals,
            )
        )

    # =========================================================================
    # _compute_fremdrift() — den viktigste. Deler på antall punkter.
    # =========================================================================

    def test_fremdrift_uten_punkter_er_null_ikke_krasj(self):
        """🔴 RANDTILFELLE: null-divisjon. Dette er den NORMALE tilstanden.

        En sjekkliste uten punkter er nøyaktig det brukeren har rett etter «ny
        sjekkliste». Deler koden 100.0 * 0 / 0 får hun ZeroDivisionError midt i
        skjemaet — ikke ved en sjelden datafeil, men ved helt vanlig bruk.

        Vernet er `if r.antall_punkt else 0.0` i _compute_fremdrift. Fjernes det,
        skal denne testen stoppe det.
        """
        liste = self._lag_liste()
        self.assertEqual(liste.antall_punkt, 0)
        self.assertEqual(liste.antall_utfort, 0)
        self.assertEqual(
            liste.fremdrift, 0.0, "Tom sjekkliste skal gi 0 %, ikke divisjon på null"
        )

    def test_fremdrift_null_holder_etter_at_siste_punkt_slettes(self):
        """🔴 Samme null-divisjon, men via den STIEN som faktisk treffer i drift.

        Å opprette en tom liste er én vei til 0 punkter. Den andre — og den som
        overrasker — er at brukeren sletter det siste punktet. Da må compute kjøre
        PÅ NYTT med antall_punkt = 0. En vakt som bare virker ved create ville
        sluppet denne igjennom.
        """
        liste = self._lag_liste()
        punkter = self._lag_punkter(liste, 3, utfort=True)
        self.assertEqual(liste.fremdrift, 100.0)
        punkter.unlink()
        self.assertEqual(liste.antall_punkt, 0)
        self.assertEqual(
            liste.fremdrift,
            0.0,
            "Etter at siste punkt er slettet må fremdrift falle til 0, ikke krasje",
        )

    def test_fremdrift_alle_utfort_er_hundre(self):
        """Alle punkter utført = 100 %. Ikke 99,999 og ikke 1.0 (andel vs prosent)."""
        liste = self._lag_liste()
        self._lag_punkter(liste, 5, utfort=True)
        self.assertEqual(liste.antall_punkt, 5)
        self.assertEqual(liste.antall_utfort, 5)
        self.assertAlmostEqual(
            liste.fremdrift,
            100.0,
            places=2,
            msg="Feltet heter «Fremdrift (%)» — 100, ikke 1.0",
        )

    def test_fremdrift_halvparten_utfort_er_femti(self):
        """2 av 4 utført = 50 %."""
        liste = self._lag_liste()
        self._lag_punkter(liste, 4)
        liste.punkt_ids[:2].write({"utfort": True})
        self.assertEqual(liste.antall_punkt, 4)
        self.assertEqual(liste.antall_utfort, 2)
        self.assertAlmostEqual(liste.fremdrift, 50.0, places=2)

    def test_fremdrift_ingen_utfort_er_null_men_punktene_telles(self):
        """0 % med punkter må skilles fra 0 % uten punkter.

        Begge viser «0 %», men de betyr helt forskjellige ting: «ingenting gjort
        ennå» mot «lista er tom». Derfor må antall_punkt skille dem.
        """
        liste = self._lag_liste()
        self._lag_punkter(liste, 3)
        self.assertEqual(
            liste.antall_punkt, 3, "Punktene skal telles selv om ingen er utført"
        )
        self.assertEqual(liste.antall_utfort, 0)
        self.assertEqual(liste.fremdrift, 0.0)

    def test_fremdrift_oppdateres_naar_punkt_hukes_av(self):
        """Compute er @api.depends på punkt_ids.utfort — den må faktisk trigges.

        Uten avhengigheten på selve `utfort`-feltet ville tallet stått stille til
        noe annet rørte lista. Brukeren huker av, ingenting skjer, og hun huker av
        på nytt.
        """
        liste = self._lag_liste()
        punkter = self._lag_punkter(liste, 2)
        self.assertEqual(liste.fremdrift, 0.0)
        punkter[0].utfort = True
        self.assertAlmostEqual(liste.fremdrift, 50.0, places=2)
        punkter[1].utfort = True
        self.assertAlmostEqual(liste.fremdrift, 100.0, places=2)
        punkter[0].utfort = False
        self.assertAlmostEqual(
            liste.fremdrift,
            50.0,
            places=2,
            msg="Å fjerne avhukingen må også regne om — ikke bare å sette den",
        )

    def test_fremdrift_avrunder_ikke_bort_udelelig_brok(self):
        """1 av 3 = 33,33… %. Feltet er Float — verdien skal ikke bli 33 eller 0.

        En Integer her ville rundet 33,33 til 33 og 66,67 til 66; på en liste med
        3 punkter ser «66 %» ut som om ett punkt mangler mer enn det gjør.
        """
        liste = self._lag_liste()
        punkter = self._lag_punkter(liste, 3)
        punkter[0].utfort = True
        self.assertAlmostEqual(liste.fremdrift, 100.0 / 3.0, places=4)

    def test_fremdrift_er_uavhengig_per_sjekkliste(self):
        """🔴 Compute løper over `self` som recordset — en løkke-feil ville smittet.

        Regnes to lister i samme batch (som Odoo gjør ved listevisning), må hver
        beholde sitt eget tall. Bruker koden en variabel utenfor løkka, får begge
        listene den sistes verdi.
        """
        tom = self._lag_liste()
        full = self._lag_liste()
        self._lag_punkter(full, 4, utfort=True)
        halv = self._lag_liste()
        self._lag_punkter(halv, 2)
        halv.punkt_ids[0].utfort = True

        # Tving samlet omregning slik listevisningen gjør det.
        batch = tom | full | halv
        batch.invalidate_recordset(["antall_punkt", "antall_utfort", "fremdrift"])
        self.assertEqual(tom.fremdrift, 0.0)
        self.assertAlmostEqual(full.fremdrift, 100.0, places=2)
        self.assertAlmostEqual(halv.fremdrift, 50.0, places=2)

    def test_punkt_arver_firma_fra_sjekklista(self):
        """company_id på punktet er related+store — record rules filtrerer på den.

        Er den tom, faller punktet utenfor firma-regelen og blir synlig på tvers.
        """
        liste = self._lag_liste()
        punkt = self._lag_punkter(liste, 1)
        self.assertEqual(punkt.company_id, liste.company_id)
        self.assertEqual(
            liste.company_id,
            self.env.company,
            "Firma skal komme fra sesjonen — aldri fra klienten",
        )

    def test_punkter_slettes_med_sjekklista(self):
        """ondelete=«cascade»: punkter uten sjekkliste er foreldreløse rader.

        `sjekkliste_id` er required — en løs cascade ville etterlatt rader som
        ingen visning kan nå, men som fortsatt telles av search_count.
        """
        liste = self._lag_liste()
        self._lag_punkter(liste, 3)
        punkt_ids = liste.punkt_ids.ids
        liste.unlink()
        self.assertFalse(
            self.Punkt.browse(punkt_ids).exists(),
            "Punkter skal følge sjekklista i grava",
        )

    # =========================================================================
    # _compute_antall() på krav
    # =========================================================================

    def test_antall_uten_kontroller_og_avvik_er_null(self):
        """🔴 RANDTILFELLE: et nyopprettet krav har ingen relasjoner.

        len() på et tomt recordset er 0, ikke False — men et krav som viser tomt
        felt i stedet for 0 leses som «ikke målt» av en revisor.
        """
        krav = self._lag_krav()
        self.assertEqual(krav.kontroll_antall, 0)
        self.assertEqual(krav.avvik_aapne, 0)

    def test_antall_kontroller_telles(self):
        """Many2many begge veier: kontrollen kobles fra kontroll-siden, telles på krav-siden."""
        krav = self._lag_krav()
        k1 = self._lag_kontroll(krav_ids=[(6, 0, krav.ids)])
        self.assertEqual(krav.kontroll_antall, 1)
        self._lag_kontroll(krav_ids=[(6, 0, krav.ids)])
        self.assertEqual(krav.kontroll_antall, 2)
        k1.krav_ids = [(5, 0, 0)]
        self.assertEqual(
            krav.kontroll_antall, 1, "Å koble fra en kontroll må også regne om"
        )

    def test_aapne_avvik_teller_kun_ikke_lukkede(self):
        """🔴 Kjernen i «åpne avvik»: lukkede skal IKKE telle.

        Telles de, ser et krav som er ryddet opp i ut som om det fortsatt har
        avvik — og et styringssystem som aldri blir grønt slutter man å se på.
        """
        krav = self._lag_krav()
        self._lag_avvik(krav_id=krav.id, status="aapen")
        self._lag_avvik(krav_id=krav.id, status="under_tiltak")
        lukket = self._lag_avvik(krav_id=krav.id, status="lukket")
        self.assertEqual(
            krav.avvik_aapne,
            2,
            "«Under tiltak» er ÅPENT — kun «lukket» skal trekkes fra",
        )
        self.assertEqual(
            len(krav.avvik_ids), 3, "Alle tre er fortsatt koblet til kravet"
        )
        self.assertTrue(lukket)

    def test_lukking_av_avvik_reduserer_aapne(self):
        """action_lukk() må slå igjennom på kravets teller — og stemple dato."""
        krav = self._lag_krav()
        avvik = self._lag_avvik(krav_id=krav.id, status="aapen")
        self.assertEqual(krav.avvik_aapne, 1)
        avvik.action_lukk()
        self.assertEqual(avvik.status, "lukket")
        self.assertEqual(
            avvik.lukket_dato,
            fields.Date.context_today(avvik),
            "Lukket-dato må stemples — ellers mangler sporet i ISO-revisjon",
        )
        self.assertEqual(krav.avvik_aapne, 0)

    def test_antall_er_uavhengig_per_krav(self):
        """Samme løkke-felle som for fremdrift, på _compute_antall."""
        tomt = self._lag_krav()
        med = self._lag_krav()
        self._lag_kontroll(krav_ids=[(6, 0, med.ids)])
        self._lag_avvik(krav_id=med.id, status="aapen")

        batch = tomt | med
        batch.invalidate_recordset(["kontroll_antall", "avvik_aapne"])
        self.assertEqual(tomt.kontroll_antall, 0)
        self.assertEqual(tomt.avvik_aapne, 0)
        self.assertEqual(med.kontroll_antall, 1)
        self.assertEqual(med.avvik_aapne, 1)

    # =========================================================================
    # resolve_taksonomi() — feature-detektert oppslag
    # =========================================================================

    def test_resolve_taksonomi_uten_kode_gir_tomt_svar(self):
        """🔴 RANDTILFELLE: krav uten taksonomi-kode.

        Metoden skal svare med kontraktens to nøkler satt til False — ikke kaste,
        og ikke returnere None. GUI-et leser nøklene direkte; None gir TypeError.
        """
        krav = self._lag_krav()
        res = krav.resolve_taksonomi()
        self.assertIsInstance(res, dict)
        self.assertIn("code_list_item_id", res)
        self.assertIn("documents_tag_id", res)
        self.assertFalse(res["code_list_item_id"])
        self.assertFalse(res["documents_tag_id"])

    def test_resolve_taksonomi_ukjent_kode_gir_false_ikke_krasj(self):
        """🔴 Ukjent verdi: koden finnes på kravet, men ikke i taksonomien.

        Dette er den vanlige tilstanden ved import — noen har tastet «99.99.99».
        Svaret skal være False (fant ikke), ikke et unntak og ikke en tilfeldig
        annen post. search(..., limit=1) på et tomt treff gir tomt recordset;
        `if item` fanger det.
        """
        krav = self._lag_krav(
            taksonomi_kode="ZZ.99.99-finnes-ikke",
            dokumentetikett=f"Etikett som ikke finnes {self._unik()}",
        )
        res = krav.resolve_taksonomi()
        self.assertFalse(
            res["code_list_item_id"],
            "Ukjent kode skal gi False — ikke et tilfeldig treff",
        )
        self.assertFalse(res["documents_tag_id"])

    def test_resolve_taksonomi_finner_kjent_verdi_naar_modellen_finnes(self):
        """Kjent verdi: finnes modellen i basen, SKAL oppslaget treffe.

        Modulen er feature-detektert (installerbar uten Documents/base_code_list),
        så testen hopper over når modellen ikke finnes — det er en ærlig melding
        om at betingelsen ikke kunne produseres her, ikke en falsk grønn.
        """
        truffet = False

        if "code.list.item" in self.env:
            kode = f"FIQ.TEST.{self._unik()}"
            item = self._lag_code_list_item(kode)
            if item:
                krav = self._lag_krav(taksonomi_kode=kode)
                self.assertEqual(krav.resolve_taksonomi()["code_list_item_id"], item.id)
                truffet = True

        if "documents.tag" in self.env:
            navn = f"FIQ Testetikett {self._unik()}"
            tag = self._lag_documents_tag(navn)
            if tag:
                krav = self._lag_krav(dokumentetikett=navn)
                self.assertEqual(krav.resolve_taksonomi()["documents_tag_id"], tag.id)
                truffet = True

        if not truffet:
            self.skipTest(
                "hverken code.list.item eller documents.tag kunne opprettes "
                "her — taksonomi-koblingen er feature-detektert (soft)"
            )

    def _lag_code_list_item(self, kode):
        """Oppretter et taksonomi-element hvis modellen finnes og lar seg fylle.

        Feltoppsettet på code.list.item eies av en annen modul; vi verifiserer
        hvilke felt som faktisk finnes i stedet for å anta dem.
        """
        Item = self.env["code.list.item"]
        vals = {"code": kode}
        if "name" in Item._fields:
            vals["name"] = f"FIQ testkode {kode}"
        try:
            return Item.create(vals)
        except Exception:
            return False

    def _lag_documents_tag(self, navn):
        """Oppretter en dokumentetikett hvis modellen finnes.

        documents.tag krever normalt en facet/kategori som eies av Documents
        (Enterprise). Klarer vi ikke å lage den, hopper testen — vi later ikke som.
        """
        Tag = self.env["documents.tag"]
        vals = {"name": navn}
        try:
            return Tag.create(vals)
        except Exception:
            return False

    def test_resolve_taksonomi_krever_en_post(self):
        """ensure_one(): metoden er skrevet for ÉN post og må si fra ved flere.

        Kalles den på et recordset, ville `self.taksonomi_kode` kastet uansett —
        men med en uforståelig feilmelding. ensure_one gir den forståelige.
        """
        krav = self._lag_krav() | self._lag_krav()
        with self.assertRaises(ValueError):
            krav.resolve_taksonomi()

    # =========================================================================
    # get_mgmtsystem_data() — API-et GUI/AI KR leser
    # =========================================================================

    def test_get_data_har_kontraktens_nokler(self):
        """Mangler en nøkkel, får KR en KeyError og mister hele boksen."""
        d = self.Krav.get_mgmtsystem_data()
        for felt in (
            "antall_krav",
            "antall_kontroller",
            "antall_sjekklister",
            "aapne_avvik",
            "krav",
        ):
            self.assertIn(
                felt, d, f"get_mgmtsystem_data mangler kontraktsfeltet {felt!r}"
            )
        self.assertIsInstance(d["krav"], list)
        self.assertIsInstance(d["antall_krav"], int)

    def test_get_data_uten_standard_tar_med_alle_standarder(self):
        """Uten parameter skal ALLE standarder være med — ikke bare ISO 9001.

        Standardfeltet har default «iso9001»; en filtrering som smyger seg inn
        ville gjort miljø- og informasjonssikkerhetskravene usynlige uten at noen
        merket det (de er i mindretall i basen).
        """
        k9 = self._lag_krav(standard="iso9001")
        k14 = self._lag_krav(standard="iso14001")
        k27 = self._lag_krav(standard="iso27001")

        ider = [r["id"] for r in self.Krav.get_mgmtsystem_data()["krav"]]
        for krav in (k9, k14, k27):
            self.assertIn(
                krav.id, ider, "Uten standard-parameter skal alle standarder være med"
            )

    def test_get_data_med_standard_filtrerer(self):
        """Med parameter skal KUN den standarden være med."""
        k9 = self._lag_krav(standard="iso9001")
        k14 = self._lag_krav(standard="iso14001")

        d = self.Krav.get_mgmtsystem_data(standard="iso14001")
        ider = [r["id"] for r in d["krav"]]
        self.assertIn(k14.id, ider)
        self.assertNotIn(k9.id, ider, "Filteret slipper igjennom feil standard")
        self.assertEqual(
            d["antall_krav"],
            len(d["krav"]),
            "antall_krav må telle det samme som lista faktisk inneholder",
        )

    def test_get_data_ukjent_standard_gir_tomt_ikke_krasj(self):
        """🔴 RANDTILFELLE: en standard som ikke finnes.

        GUI-et kan sende en verdi fra en gammel meny. Svaret skal være en tom
        liste med gyldig struktur — ikke et unntak, og ikke «alle krav» (som ville
        vært den farlige feilen: filteret ignoreres stille).
        """
        self._lag_krav(standard="iso9001")
        d = self.Krav.get_mgmtsystem_data(standard="finnes_ikke")
        self.assertEqual(d["krav"], [], "Ukjent standard skal gi tomt, ikke alt")
        self.assertEqual(d["antall_krav"], 0)
        self.assertIsInstance(d["aapne_avvik"], int)

    def test_get_data_utelater_inaktive_krav(self):
        """aktiv = False betyr «utgått klausul» — den skal ikke telles som gjeldende."""
        aktivt = self._lag_krav()
        utgatt = self._lag_krav(aktiv=False)
        ider = [r["id"] for r in self.Krav.get_mgmtsystem_data()["krav"]]
        self.assertIn(aktivt.id, ider)
        self.assertNotIn(utgatt.id, ider, "Utgått krav skal ikke telles som gjeldende")

    def test_get_data_gir_navn_ikke_bare_id(self):
        """Husets regel: navn, ikke ID, i visningsfelt.

        Radene må bære lesbar tekst — og `standard` skal være ETIKETTEN
        («ISO 9001 — Kvalitet»), ikke den tekniske nøkkelen «iso9001».
        """
        krav = self._lag_krav(standard="iso14001", klausul=f"14.{self._unik()}")
        rad = [r for r in self.Krav.get_mgmtsystem_data()["krav"] if r["id"] == krav.id]
        self.assertTrue(rad, "Kravet testen opprettet mangler i svaret")
        rad = rad[0]
        self.assertEqual(rad["navn"], krav.name)
        self.assertEqual(
            rad["standard"],
            "ISO 14001 — Miljø",
            "«standard» skal være etiketten, ikke den tekniske nøkkelen",
        )

    def test_get_data_taaler_tomme_tekstfelt(self):
        """🔴 RANDTILFELLE: klausul og taksonomi-kode er valgfrie → False i basen.

        `or ""` i koden gjør False om til tom streng. Fjernes den, sender API-et
        `false` der GUI-et venter tekst — og front-enden skriver «false» på skjermen
        eller krasjer på .trim(). Klassisk data-betinget krasj som en test på en
        base med fullstendige data aldri ser.
        """
        krav = self._lag_krav(klausul=False, taksonomi_kode=False)
        rad = [
            r for r in self.Krav.get_mgmtsystem_data()["krav"] if r["id"] == krav.id
        ][0]
        self.assertEqual(
            rad["klausul"], "", "Tom klausul skal bli tom streng, ikke False"
        )
        self.assertEqual(rad["taksonomi_kode"], "")
        self.assertIsInstance(rad["klausul"], str)
        self.assertIsInstance(rad["taksonomi_kode"], str)

    def test_get_data_teller_kontroller_og_sjekklister(self):
        """Aggregatene måles som DIFFERANSE — basen kan alt inneholde poster."""
        for_ = self.Krav.get_mgmtsystem_data()
        self._lag_kontroll()
        self._lag_kontroll()
        liste = self._lag_liste()
        self._lag_punkter(liste, 2)

        etter = self.Krav.get_mgmtsystem_data()
        self.assertEqual(etter["antall_kontroller"] - for_["antall_kontroller"], 2)
        self.assertEqual(etter["antall_sjekklister"] - for_["antall_sjekklister"], 1)

    def test_get_data_teller_aapne_avvik_ikke_lukkede(self):
        """Samme skille som på kravet, men på aggregatnivå."""
        for_ = self.Krav.get_mgmtsystem_data()["aapne_avvik"]
        self._lag_avvik(status="aapen")
        self._lag_avvik(status="under_tiltak")
        self._lag_avvik(status="lukket")
        etter = self.Krav.get_mgmtsystem_data()["aapne_avvik"]
        self.assertEqual(
            etter - for_, 2, "Kun «lukket» skal trekkes fra — «under tiltak» er åpent"
        )

    def test_get_data_radenes_tall_stemmer_med_kravet(self):
        """Radene i API-svaret må bære SAMME tall som posten — ikke et eget regnestykke."""
        krav = self._lag_krav()
        self._lag_kontroll(krav_ids=[(6, 0, krav.ids)])
        self._lag_avvik(krav_id=krav.id, status="aapen")
        self._lag_avvik(krav_id=krav.id, status="lukket")

        rad = [
            r for r in self.Krav.get_mgmtsystem_data()["krav"] if r["id"] == krav.id
        ][0]
        self.assertEqual(rad["kontroller"], krav.kontroll_antall)
        self.assertEqual(rad["aapne_avvik"], krav.avvik_aapne)
        self.assertEqual(rad["aapne_avvik"], 1)

    def test_get_data_taaler_tom_base(self):
        """🔴 Uten ett eneste krav skal API-et svare, ikke krasje.

        Dev bygger fra tom base — helt andre data enn Staging. Metoden må gi en
        gyldig, tom struktur. Testen bruker et firma-scope der ingenting finnes.
        """
        firma = self._annet_firma()
        bruker = self._bruker_i(firma)
        d = self.Krav.with_user(bruker).with_company(firma).get_mgmtsystem_data()
        self.assertEqual(d["krav"], [])
        self.assertEqual(d["antall_krav"], 0)
        self.assertEqual(d["aapne_avvik"], 0)
        self.assertIsInstance(d["antall_kontroller"], int)

    # =========================================================================
    # TENANT-ISOLASJON — record rules, ikke AI-atferd (kanon)
    # =========================================================================

    def _annet_firma(self):
        """Et firma som IKKE er sesjonens. Skiper hvis det ikke lar seg skaffe.

        Vi søker FØRST etter et eksisterende firma: res.company.create() drar med
        seg hver enterprise-modul som utvider modellen, og documents_project nekter
        skrivingen («Company Project Folders cannot be linked to another company»)
        — dokumentert i fiq_gui_relations/tests/test_fiq_gui_relation.py:34.
        Klarer vi hverken å finne eller lage et, skipper testen ærlig i stedet for
        å feile på noe som ikke handler om styringssystemet.
        """
        annet = self.env["res.company"].search(
            [("id", "!=", self.env.company.id)], limit=1
        )
        if annet:
            return annet
        try:
            return self.env["res.company"].create(
                {"name": f"FIQ Testfirma {self._unik()}"}
            )
        except Exception:
            self.skipTest(
                "trenger et firma nummer to; å opprette et er blokkert på "
                "denne basen (documents_project e.l.)"
            )

    def _bruker_i(self, firma):
        """En vanlig bruker som KUN tilhører `firma`.

        Testadministratoren tilhører alle firmaer, så scope må testes gjennom en
        bruker med smalere tilgang — ellers beviser testen ingenting.
        """
        return self.env["res.users"].create(
            {
                "name": f"FIQ mgmt-testbruker {self._unik()}",
                "login": f"fiq_mgmt_test_{self._unik()}",
                "company_id": firma.id,
                "company_ids": [(6, 0, [firma.id])],
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )

    def test_krav_settes_til_sesjonens_firma(self):
        """company_id kommer fra sesjonen — aldri fra klienten (kanon)."""
        for post in (
            self._lag_krav(),
            self._lag_kontroll(),
            self._lag_liste(),
            self._lag_avvik(),
        ):
            self.assertEqual(
                post.company_id, self.env.company, f"{post._name} fikk feil firma"
            )

    def test_get_data_lekker_ikke_annet_firmas_krav(self):
        """🛑 HARD GRENSE: en annen tenants krav skal ALDRI komme med.

        Kanon: Odoo håndhever tenant-isolasjon gjennom record rules — ikke
        AI-atferd. get_mgmtsystem_data tar derfor bevisst INGEN firma-parameter;
        scopet kommer fra sesjonen. Denne testen låser at regelen faktisk virker
        når API-et kalles av en bruker i et annet firma.
        """
        firma_b = self._annet_firma()
        bruker_b = self._bruker_i(firma_b)

        mitt = self._lag_krav()  # firma A (sesjonen)
        deres = self._lag_krav(company_id=firma_b.id)

        d = self.Krav.with_user(bruker_b).with_company(firma_b).get_mgmtsystem_data()
        ider = [r["id"] for r in d["krav"]]
        self.assertIn(deres.id, ider, "Eget firmas krav må være synlig")
        self.assertNotIn(
            mitt.id, ider, "🛑 TENANT-LEKKASJE: annet firmas krav kom med i API-svaret"
        )

    def test_generisk_mal_uten_firma_er_delt(self):
        """company_id = False er en GENERISK MAL — bevisst delt på tvers.

        Regelen er ['|',('company_id','=',False),('company_id','in',company_ids)].
        Det er ikke en lekkasje, det er hele poenget med maler: FIQ vedlikeholder
        ISO-klausulene ETT sted i stedet for å kopiere dem per kunde.
        """
        firma_b = self._annet_firma()
        bruker_b = self._bruker_i(firma_b)
        mal = self._lag_krav(company_id=False)

        ider = [
            r["id"]
            for r in self.Krav.with_user(bruker_b)
            .with_company(firma_b)
            .get_mgmtsystem_data()["krav"]
        ]
        self.assertIn(
            mal.id, ider, "Generisk mal (company_id=False) skal være synlig for alle"
        )

    def test_aggregatene_er_ogsaa_firma_scopet(self):
        """🛑 Tellerne bruker search_count — de må lyde de samme reglene.

        Et krav-tall som er scopet, men et avviks-tall som ikke er det, er verre
        enn ingen tall: forsiden ser konsistent ut og er det ikke.
        """
        firma_b = self._annet_firma()
        bruker_b = self._bruker_i(firma_b)

        for_ = self.Krav.with_user(bruker_b).with_company(firma_b).get_mgmtsystem_data()
        # Opprett i firma A — B skal ikke se noen av dem.
        self._lag_kontroll()
        self._lag_liste()
        self._lag_avvik(status="aapen")
        etter = (
            self.Krav.with_user(bruker_b).with_company(firma_b).get_mgmtsystem_data()
        )

        self.assertEqual(
            etter["antall_kontroller"],
            for_["antall_kontroller"],
            "🛑 Kontroll-telleren lekker over firmagrensen",
        )
        self.assertEqual(
            etter["antall_sjekklister"],
            for_["antall_sjekklister"],
            "🛑 Sjekkliste-telleren lekker over firmagrensen",
        )
        self.assertEqual(
            etter["aapne_avvik"],
            for_["aapne_avvik"],
            "🛑 Avviks-telleren lekker over firmagrensen",
        )

    def test_sjekklistepunkt_er_firma_scopet(self):
        """Punktets company_id er related+store nettopp for at regelen skal treffe."""
        firma_b = self._annet_firma()
        bruker_b = self._bruker_i(firma_b)

        liste = self._lag_liste()  # firma A
        punkter = self._lag_punkter(liste, 2)
        synlige = self.Punkt.with_user(bruker_b).with_company(firma_b).search([])
        for p in punkter:
            self.assertNotIn(
                p, synlige, "🛑 TENANT-LEKKASJE: annet firmas sjekklistepunkt er synlig"
            )

    # =========================================================================
    # Datamodell-vakter
    # =========================================================================

    def test_klausul_er_unik_per_standard_og_firma(self):
        """Duplikat klausul innen samme standard+firma skal avvises av basen.

        To poster for «7.5» betyr at revisoren ser samme klausul to ganger med
        ulike tall — og ikke vet hvilken som gjelder.
        """
        from psycopg2 import IntegrityError

        u = self._unik()
        self.Krav.create({"name": "Første", "klausul": f"7.{u}", "standard": "iso9001"})
        with self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.Krav.create(
                    {"name": "Duplikat", "klausul": f"7.{u}", "standard": "iso9001"}
                )

    def test_samme_klausul_i_ulik_standard_er_lov(self):
        """«7.5» finnes i BÅDE ISO 9001 og ISO 14001 — det er ikke et duplikat."""
        u = self._unik()
        a = self.Krav.create(
            {"name": "9001-7.5", "klausul": f"7.{u}", "standard": "iso9001"}
        )
        b = self.Krav.create(
            {"name": "14001-7.5", "klausul": f"7.{u}", "standard": "iso14001"}
        )
        self.assertNotEqual(a.id, b.id)

    def test_avvik_overlever_at_kravet_slettes(self):
        """ondelete=«set null»: historikken skal ikke forsvinne med klausulen.

        Slettes et krav, må avviket bestå — det er dokumentert informasjon
        (ISO 9001 §7.5). En cascade her ville slettet revisjonssporet.
        """
        krav = self._lag_krav()
        avvik = self._lag_avvik(krav_id=krav.id, status="aapen")
        krav.unlink()
        self.assertTrue(avvik.exists(), "Avviket skal overleve at kravet slettes")
        self.assertFalse(avvik.krav_id)
