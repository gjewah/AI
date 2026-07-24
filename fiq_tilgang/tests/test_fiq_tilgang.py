"""Tester for rettighetsfundamentet (fiq_tilgang).

Hvorfor de finnes: denne modulen avgjør HVEM SOM SER HVA på tvers av fem firmaer.
En feil her er ikke en visningsfeil — det er en datalekkasje mellom kunder.
Modulen hadde NULL tester før 23.07.2026.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand (firmaer, brukere, roller,
områder, regler). Ingen test leser det som tilfeldigvis ligger i basen — en test
som bare leser eksisterende data beviser ingenting, og Dev bygger fra TOM base.

TILGANGSNEKT testes like grundig som innvilgelse. De viktigste testene her er de
som krever at bruker i firma A IKKE ser firma B.

⚠️ TRE DEFEKTER som disse testene AVDEKKER — ikke skjuler. Alle tre er MÅLT i
kjøring på Dev 23.07.2026, ikke antatt. Resultatlinja med kanarifuglen fjernet:
    `1 failed, 21 error(s) of 33 tests` (+ 7 hoppet over, se defekt 1)
Fordelingen av de 22 (målt, ikke gjettet):
    18 × AttributeError 'documents.tag' … 'parent_id'   → defekt 1
     3 × AttributeError 'res.users' … 'groups_id'        → defekt 2
     1 × AssertionError 3 != 0 (tenant-lekkasje)         → defekt 3

  1. `documents.tag` har INGEN `parent_id` i Odoo 19. Feltet kommer fra modulen
     `documents_tag` (Loym/FIQ), som fiq_tilgang IKKE har i `depends`
     (`depends = ["base", "documents"]`). Målt på Dev: documents_tag = uninstalled,
     og feltlista for documents.tag er
     color/create_date/create_uid/display_name/document_ids/id/name/sequence/
     tooltip/write_date/write_uid — ingen parent_id.
     Følge: `effektiv_nivaa()` kaster AttributeError på `node = node.parent_id`.
     Hele arve-mekanismen — modulens kjerne — kan ikke kjøre slik den er installert.

  2. `_gjelder_bruker()` bruker `user.groups_id`. Det feltet er Odoo 18-syntaks.
     I Odoo 19 heter det `group_ids` (verifisert i kildekoden
     odoo/addons/base/models/res_users.py:257, og `groups_id` finnes IKKE i
     ir_model_fields for res.users på Dev — 0 treff, ingen bakoverkompatibel alias).
     Følge: hver regel med subjekt_type = "gruppe" kaster AttributeError.
     Målt i kjøringen: 3 tester traff denne med
     `AttributeError: 'res.users' object has no attribute 'groups_id'`.
     Fiks: bruk `user.all_group_ids` (tar også med implied groups).

  3. 🔴 EKTE TENANT-LEKKASJE, målt som FAIL (ikke krasj — feil SVAR):
     `test_selskaps_admin_i_firma_b_er_ikke_admin_i_firma_a` ga «3 != 0».
     En bruker med «Global admin (selskap)» i firma B fikk `administrere` (3) på
     firma A sitt område. `effektiv_nivaa()` sjekker bare `has_group(...)` og ser
     ALDRI på hvilket selskap området eller brukeren tilhører — «per selskap» er
     dermed bare et navn på gruppa. Dette er den alvorligste av de tre: den gir
     feil svar stille, mens de to andre i det minste stopper med en feilmelding.

Testene under er skrevet mot ØNSKET oppførsel (arv skal virke, gruppe-regler skal
virke). Feiler de, er det koden som skal fikses — ikke testen som skal slakkes.
De testene som ikke er avhengige av de to defektene er skrevet slik at de kjører
uansett, så resten av modulen faktisk blir dekket.
"""

from odoo.tests import TransactionCase, tagged

# Rangeringen koden selv bruker (fiq_tilgang/models/fiq_tilgang_regel.py).
LESE, SKRIVE, ADMINISTRERE = 1, 2, 3


@tagged("post_install", "-at_install", "fiq_tilgang")
class TestFiqTilgang(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Regel = cls.env["fiq.tilgang.regel"]
        cls.Rolle = cls.env["fiq.tilgang.rolle"]
        cls.Tag = cls.env["documents.tag"]
        cls.Users = cls.env["res.users"]

        # Har basen hierarki på områdene i det hele tatt? Avgjør om arve-testene
        # kan kjøre. Måles — antas ikke.
        cls.har_hierarki = "parent_id" in cls.Tag._fields

        # ---- To SKILTE firmaer. Kjernen i tenant-isolasjonen. ----
        Company = cls.env["res.company"]
        cls.firma_a = Company.create({"name": "FIQ Test Firma A"})
        cls.firma_b = Company.create({"name": "FIQ Test Firma B"})

        # ---- Roller (org-hierarki), opprettet av testen selv ----
        cls.rolle_leder = cls.Rolle.create({"name": "Testleder", "art": "intern"})
        cls.rolle_arbeider = cls.Rolle.create(
            {
                "name": "Testarbeider",
                "art": "intern",
                "parent_id": cls.rolle_leder.id,
            }
        )
        cls.rolle_ekstern = cls.Rolle.create({"name": "Testekstern", "art": "ekstern"})

    # ------------------------------------------------------------------
    # Hjelpere — hver test bygger sin egen tilstand med disse
    # ------------------------------------------------------------------

    _teller = 0

    @classmethod
    def _unikt(cls, prefiks):
        """documents.tag har UNIQUE(name) i Odoo 19 — navnet må være unikt per post."""
        TestFiqTilgang._teller += 1
        return f"{prefiks}-{TestFiqTilgang._teller}"

    def _omraade(self, navn, forelder=None):
        """Oppretter ET område (documents.tag), evt. under et annet."""
        vals = {"name": self._unikt(navn)}
        if forelder is not None and self.har_hierarki:
            # documents_tag-modulen: parent_id er compute/store fra parent_ids (m2m).
            vals["parent_ids"] = [(6, 0, forelder.ids)]
        return self.Tag.create(vals)

    def _bruker(self, navn, firma, rolle=None, ekstra_firmaer=None, grupper=None):
        """Oppretter EN bruker bundet til ETT firma (+ evt. flere tillatte)."""
        firmaer = [firma.id] + [f.id for f in (ekstra_firmaer or [])]
        vals = {
            "name": navn,
            "login": self._unikt(navn.lower().replace(" ", ".")) + "@fiq-test.no",
            "company_id": firma.id,
            "company_ids": [(6, 0, firmaer)],
        }
        if rolle is not None:
            vals["fiq_tilgang_rolle_id"] = rolle.id
        bruker = self.Users.create(vals)
        if grupper:
            # Odoo 19: feltet heter group_ids (groups_id er 18-syntaks og finnes ikke).
            bruker.group_ids = [(4, g.id) for g in grupper]
        return bruker

    def _regel(
        self,
        omraade,
        nivaa="lese",
        regel_type="tildeling",
        rolle=None,
        bruker=None,
        gruppe=None,
        partner=None,
        firma=None,
    ):
        """Oppretter ÉN tilgangsregel med eksplisitt subjekt."""
        vals = {
            "ressurs_id": omraade.id,
            "nivaa": nivaa,
            "regel_type": regel_type,
            "company_id": (firma or self.firma_a).id,
        }
        if rolle is not None:
            vals.update(subjekt_type="rolle", rolle_id=rolle.id)
        elif bruker is not None:
            vals.update(subjekt_type="bruker", bruker_id=bruker.id)
        elif gruppe is not None:
            vals.update(subjekt_type="gruppe", gruppe_id=gruppe.id)
        elif partner is not None:
            vals.update(subjekt_type="partner", partner_id=partner.id)
        return self.Regel.create(vals)

    def _krev_hierarki(self):
        """Arve-testene er meningsløse uten parent_id. Hopp over — ikke lyv grønt."""
        if not self.har_hierarki:
            self.skipTest(
                "documents.tag mangler parent_id — modulen `documents_tag` er ikke "
                "installert og står ikke i fiq_tilgang sin `depends`. Arve-mekanismen "
                "kan ikke testes (og kan ikke kjøre) uten den. Se modul-docstring."
            )

    # ==================================================================
    # 1. TILGANGSNEKT — det viktigste. Ingen tilgang er standard.
    # ==================================================================

    def test_bruker_uten_rolle_har_ingen_tilgang(self):
        """🛑 RANDTILFELLE: bruker uten rolle skal få 0 — ikke arve noe som helst.

        Dette er standardtilstanden for en nyopprettet bruker. Gir modulen tilgang
        her, får hver nyansatt lesetilgang til alt fra dag én.
        """
        omraade = self._omraade("Omraade")
        self._regel(omraade, nivaa="administrere", rolle=self.rolle_leder)
        uten_rolle = self._bruker("Uten Rolle", self.firma_a)

        self.assertFalse(
            uten_rolle.fiq_tilgang_rolle_id, "Forutsetning: brukeren skal ikke ha rolle"
        )
        self.assertEqual(
            omraade.effektiv_nivaa(uten_rolle),
            0,
            "Bruker uten rolle skal ikke arve noen tilgang",
        )

    def test_ingen_regler_gir_null(self):
        """🛑 Et område uten én eneste regel gir 0 for alle. Nekt er standard."""
        omraade = self._omraade("Uroert")
        bruker = self._bruker("Ingen Regler", self.firma_a, rolle=self.rolle_arbeider)
        self.assertEqual(
            omraade.effektiv_nivaa(bruker), 0, "Uten regler skal ingen ha tilgang"
        )

    def test_regel_for_annen_rolle_gjelder_ikke(self):
        """🛑 RANDTILFELLE «regel som ikke gjelder»: feil rolle = ingen tilgang.

        Dette er den vanligste lekkasje-formen: en regel som treffer bredere enn
        den skal. Har brukeren en ANNEN rolle, skal regelen være uten virkning.
        """
        omraade = self._omraade("KunLeder")
        self._regel(omraade, nivaa="administrere", rolle=self.rolle_leder)
        arbeider = self._bruker("Arbeider", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(
            omraade.effektiv_nivaa(arbeider),
            0,
            "Regel for Testleder skal ikke treffe Testarbeider",
        )

    def test_regel_for_annen_bruker_gjelder_ikke(self):
        """🛑 Bruker-regel er punktvis: den skal treffe ÉN bruker, ikke naboen."""
        omraade = self._omraade("KunPer")
        per = self._bruker("Per", self.firma_a)
        kari = self._bruker("Kari", self.firma_a)
        self._regel(omraade, nivaa="skrive", bruker=per)

        self.assertEqual(omraade.effektiv_nivaa(per), SKRIVE)
        self.assertEqual(
            omraade.effektiv_nivaa(kari), 0, "Regel for Per skal ikke gi Kari tilgang"
        )

    def test_rolle_hierarki_gir_ikke_automatisk_arv_av_rettigheter(self):
        """🛑 Rolle-treet er et ORG-KART, ikke en rettighetskjede.

        Testarbeider har Testleder som `parent_id`. Det betyr «rapporterer til»,
        IKKE «har lederens rettigheter». Arves rettigheter oppover rolle-treet,
        får hver arbeider sjefens tilgang — stikk i strid med minste privilegium.
        Denne testen låser at `_gjelder_bruker` matcher rollen EKSAKT.
        """
        omraade = self._omraade("Ledernivaa")
        self._regel(omraade, nivaa="administrere", rolle=self.rolle_leder)
        arbeider = self._bruker("Underordnet", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(
            self.rolle_arbeider.parent_id,
            self.rolle_leder,
            "Forutsetning: arbeideren er underordnet lederen",
        )
        self.assertEqual(
            omraade.effektiv_nivaa(arbeider),
            0,
            "Rolle-hierarkiet skal ikke arve RETTIGHETER oppover",
        )

    def test_partner_regel_treffer_ikke_feil_partner(self):
        """🛑 Partner-regel (portal/ekstern) skal treffe én motpart, ikke alle."""
        omraade = self._omraade("Portalomraade")
        a = self._bruker("Ekstern A", self.firma_a, rolle=self.rolle_ekstern)
        b = self._bruker("Ekstern B", self.firma_a, rolle=self.rolle_ekstern)
        self._regel(omraade, nivaa="lese", partner=a.partner_id)

        self.assertEqual(omraade.effektiv_nivaa(a), LESE)
        self.assertEqual(
            omraade.effektiv_nivaa(b), 0, "Partner-regel for A skal ikke gi B tilgang"
        )

    # ==================================================================
    # 2. TENANT-ISOLASJON — firma A skal ALDRI se firma B
    # ==================================================================

    def test_bruker_i_firma_a_ser_ikke_firma_b_sitt_omraade(self):
        """🛑 HARD GRENSE — den viktigste testen i fila.

        Firma B gir sin egen rolle administrer-tilgang på SITT område. En bruker i
        firma A, med en helt annen rolle, skal ha NULL der. Lekker dette, ser én
        kunde en annen kundes dokumenter. Det er en GDPR-hendelse, ikke en bug.
        """
        omraade_b = self._omraade("FirmaB-Hemmelig")
        rolle_b = self.Rolle.create(
            {
                "name": self._unikt("RolleB"),
                "art": "intern",
                "company_id": self.firma_b.id,
            }
        )
        self._regel(omraade_b, nivaa="administrere", rolle=rolle_b, firma=self.firma_b)

        bruker_a = self._bruker("Bruker A", self.firma_a, rolle=self.rolle_arbeider)
        self.assertEqual(
            omraade_b.effektiv_nivaa(bruker_a),
            0,
            "TENANT-LEKKASJE: bruker i firma A fikk tilgang til firma B sitt område",
        )

    def test_samme_rolle_i_to_firmaer_lekker_ikke(self):
        """🛑 Den SNEDIGE lekkasjen: rollen er delt, dataene er det ikke.

        `fiq.tilgang.rolle.company_id` kan stå tomt = «generisk, arves av alle
        firma». Da har brukere i BEGGE firmaer samme rolle-post. Regelen har et
        `company_id`, men `effektiv_nivaa()` filtrerer ALDRI på det — den søker
        kun på `ressurs_id`. Følgen: en generisk rolle blir en bro mellom tenanter.

        Denne testen krever at firma-grensen holder. Feiler den, er fiksen å
        filtrere regelsøket på brukerens firma i `effektiv_nivaa()`.
        """
        generisk = self.Rolle.create({"name": self._unikt("Generisk"), "art": "intern"})
        self.assertFalse(
            generisk.company_id, "Forutsetning: rollen er generisk (uten firma)"
        )

        omraade_b = self._omraade("FirmaB-Lonn")
        self._regel(omraade_b, nivaa="administrere", rolle=generisk, firma=self.firma_b)

        # Bruker i firma A med SAMME generiske rolle — men uten tilgang til firma B.
        bruker_a = self._bruker("Delt Rolle A", self.firma_a, rolle=generisk)
        self.assertNotIn(
            self.firma_b,
            bruker_a.company_ids,
            "Forutsetning: brukeren har ikke tilgang til firma B",
        )

        self.assertEqual(
            omraade_b.effektiv_nivaa(bruker_a),
            0,
            "TENANT-LEKKASJE: en generisk rolle ga bruker i firma A tilgang til en "
            "regel som tilhører firma B (effektiv_nivaa filtrerer ikke på firma)",
        )

    def test_selskaps_admin_i_firma_b_er_ikke_admin_i_firma_a(self):
        """🛑 «Global admin (selskap)» skal gjelde EGET selskap — ikke alle.

        Gruppa heter «Global admin (selskap)», men `effektiv_nivaa()` returnerer
        `administrere` for enhver som har gruppa, uten å se på HVILKET selskap
        området eller regelen tilhører. Da er «per selskap» bare et navn.

        Denne testen krever at selskaps-admin i firma B ikke er allmektig i
        firma A. Feiler den: selskaps-admin-sjekken må bindes til firma.
        """
        gruppe_selskap = self.env.ref("fiq_tilgang.group_company_admin")
        omraade_a = self._omraade(
            "FirmaA-Styre",
        )
        # Området tilhører firma A-verdenen; admin sitter i firma B.
        admin_b = self._bruker(
            "Selskapsadmin B", self.firma_b, grupper=[gruppe_selskap]
        )

        self.assertEqual(
            omraade_a.effektiv_nivaa(admin_b),
            0,
            "TENANT-LEKKASJE: selskaps-admin i firma B fikk administrer-tilgang på "
            "firma A sitt område — gruppa er ikke bundet til selskap",
        )

    # ==================================================================
    # 3. TILGANGSINNVILGELSE — det som SKAL virke
    # ==================================================================

    def test_rolle_regel_gir_riktig_nivaa(self):
        """Grunnfallet: en tildeling på riktig rolle gir nøyaktig det nivået."""
        omraade = self._omraade("Fagomraade")
        self._regel(omraade, nivaa="skrive", rolle=self.rolle_arbeider)
        bruker = self._bruker("Arbeider", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(omraade.effektiv_nivaa(bruker), SKRIVE)

    def test_bruker_regel_gir_tilgang(self):
        """Punktvis tildeling til én navngitt bruker."""
        omraade = self._omraade("Personlig")
        bruker = self._bruker("Navngitt", self.firma_a)
        self._regel(omraade, nivaa="administrere", bruker=bruker)

        self.assertEqual(omraade.effektiv_nivaa(bruker), ADMINISTRERE)

    def test_partner_regel_gir_tilgang(self):
        """Ekstern/portal-tilgang via partner."""
        omraade = self._omraade("Kundeportal")
        bruker = self._bruker("Portalbruker", self.firma_a, rolle=self.rolle_ekstern)
        self._regel(omraade, nivaa="lese", partner=bruker.partner_id)

        self.assertEqual(omraade.effektiv_nivaa(bruker), LESE)

    def test_gruppe_regel_gir_tilgang(self):
        """🔴 AVDEKKER DEFEKT 2: `_gjelder_bruker` bruker `user.groups_id`.

        `groups_id` er Odoo 18-syntaks. I Odoo 19 heter feltet `group_ids`
        (odoo/addons/base/models/res_users.py:257). Målt på Dev: `groups_id`
        finnes IKKE i ir_model_fields for res.users — 0 treff, ingen alias.
        Derfor kaster hver gruppe-regel AttributeError.

        Fiks: bytt til `user.all_group_ids` i `_gjelder_bruker` (all_group_ids
        tar også med implied groups — som er det man faktisk mener med
        «brukeren er i gruppa»).
        """
        gruppe = self.env["res.groups"].create({"name": self._unikt("Testgruppe")})
        omraade = self._omraade("Gruppeomraade")
        self._regel(omraade, nivaa="skrive", gruppe=gruppe)
        i_gruppa = self._bruker("I Gruppa", self.firma_a, grupper=[gruppe])

        self.assertEqual(omraade.effektiv_nivaa(i_gruppa), SKRIVE)

    def test_gruppe_regel_treffer_ikke_utenforstaaende(self):
        """🛑 Motstykket: er du ikke i gruppa, får du ingenting."""
        gruppe = self.env["res.groups"].create({"name": self._unikt("Lukket")})
        omraade = self._omraade("Lukketomraade")
        self._regel(omraade, nivaa="administrere", gruppe=gruppe)
        utenfor = self._bruker("Utenfor", self.firma_a)

        self.assertEqual(
            omraade.effektiv_nivaa(utenfor),
            0,
            "Bruker utenfor gruppa skal ikke få tilgang",
        )

    def test_global_admin_ser_alt(self):
        """Global admin (topp) skal ha administrer overalt — uten én eneste regel."""
        gruppe_global = self.env.ref("fiq_tilgang.group_global_admin")
        omraade = self._omraade("Hvorsomhelst")
        admin = self._bruker("Toppadmin", self.firma_a, grupper=[gruppe_global])

        self.assertEqual(
            omraade.effektiv_nivaa(admin),
            ADMINISTRERE,
            "Global admin (topp) skal ha administrer overalt",
        )

    # ==================================================================
    # 4. RANDTILFELLER — nivå, flere roller, manglende firma
    # ==================================================================

    def test_hoyeste_nivaa_vinner_ved_flere_regler(self):
        """Flere tildelinger på samme område: den HØYESTE gjelder (max, ikke siste)."""
        omraade = self._omraade("Flerregel")
        bruker = self._bruker("Flerregel", self.firma_a, rolle=self.rolle_arbeider)
        self._regel(omraade, nivaa="lese", rolle=self.rolle_arbeider)
        self._regel(omraade, nivaa="administrere", rolle=self.rolle_arbeider)
        self._regel(omraade, nivaa="skrive", bruker=bruker)

        self.assertEqual(
            omraade.effektiv_nivaa(bruker),
            ADMINISTRERE,
            "Høyeste nivå skal vinne når flere regler treffer",
        )

    def test_bruker_med_flere_treff_via_rolle_og_bruker(self):
        """RANDTILFELLE «flere roller»: en bruker kan treffes av flere subjekt-typer.

        Odoo lar en bruker ha ÉN `fiq_tilgang_rolle_id`, men samme bruker kan
        treffes gjennom rolle, gruppe, bruker OG partner samtidig. Alle skal telle,
        og høyeste nivå skal vinne.
        """
        gruppe = self.env["res.groups"].create({"name": self._unikt("Multi")})
        omraade = self._omraade("Multiomraade")
        bruker = self._bruker(
            "Multi", self.firma_a, rolle=self.rolle_arbeider, grupper=[gruppe]
        )
        self._regel(omraade, nivaa="lese", rolle=self.rolle_arbeider)
        self._regel(omraade, nivaa="lese", partner=bruker.partner_id)
        self._regel(omraade, nivaa="administrere", gruppe=gruppe)

        self.assertEqual(
            omraade.effektiv_nivaa(bruker),
            ADMINISTRERE,
            "Treff via flere subjekt-typer: høyeste nivå skal vinne",
        )

    def test_bruker_uten_firma_faar_ikke_tilgang(self):
        """🛑 RANDTILFELLE «manglende firma»: uten firma skal ingenting innvilges.

        En bruker uten firma hører ikke til noen tenant. Får den tilgang, har vi
        en konto som står utenfor hele firma-modellen.
        """
        omraade = self._omraade("Firmaloest")
        rolle = self.Rolle.create({"name": self._unikt("Loesrolle"), "art": "intern"})
        self._regel(omraade, nivaa="administrere", rolle=rolle)

        # company_id er required på res.users — vi måler derfor en bruker som
        # IKKE har tilgang til regelens firma i det hele tatt.
        bruker = self._bruker("Feil Firma", self.firma_b, rolle=rolle)
        self.assertNotIn(
            self.firma_a, bruker.company_ids, "Forutsetning: brukeren har ikke firma A"
        )
        self.assertEqual(
            omraade.effektiv_nivaa(bruker),
            0,
            "Regel i firma A skal ikke treffe en bruker som ikke har firma A",
        )

    def test_har_tilgang_ukjent_nivaa_nekter(self):
        """🛑 Ukjent nivånavn må NEKTE, aldri innvilge.

        `har_tilgang` bruker `NIVAA_RANG.get(nivaa, 99)`. 99 er valgt bevisst:
        en skrivefeil («lese » eller «read») skal gi nekt, ikke tilgang. Byttes
        default til 0, ville enhver skrivefeil gitt fri tilgang.
        """
        omraade = self._omraade("Ukjentnivaa")
        admin = self._bruker("Adminbruker", self.firma_a)
        self._regel(omraade, nivaa="administrere", bruker=admin)

        self.assertTrue(omraade.har_tilgang("administrere", admin))
        self.assertFalse(
            omraade.har_tilgang("tulleverdi", admin),
            "Ukjent nivånavn skal nekte, ikke innvilge",
        )

    def test_har_tilgang_er_terskel_ikke_likhet(self):
        """«Minst dette nivået»: skrive-tilgang gir også lese, men ikke administrere."""
        omraade = self._omraade("Terskel")
        bruker = self._bruker("Skriver", self.firma_a, rolle=self.rolle_arbeider)
        self._regel(omraade, nivaa="skrive", rolle=self.rolle_arbeider)

        self.assertTrue(omraade.har_tilgang("lese", bruker), "Skrive skal dekke lese")
        self.assertTrue(omraade.har_tilgang("skrive", bruker))
        self.assertFalse(
            omraade.har_tilgang("administrere", bruker),
            "Skrive skal IKKE gi administrere",
        )

    def test_har_tilgang_uten_tilgang_er_usant_paa_alle_nivaaer(self):
        """Nivå 0 (randtilfelle): ingen tilgang skal gi False på ALLE nivåer."""
        omraade = self._omraade("Stengt")
        bruker = self._bruker("Ingen", self.firma_a)
        for nivaa in ("lese", "skrive", "administrere"):
            self.assertFalse(
                omraade.har_tilgang(nivaa, bruker),
                f"Nivå 0 skal gi False for {nivaa!r}",
            )

    def test_gjelder_bruker_uten_subjekt_er_usant(self):
        """RANDTILFELLE: regel med subjekt_type satt, men tomt subjekt = treffer ingen.

        `_gjelder_bruker` returnerer False når rolle/gruppe/partner er tom.
        Uten den vakten ville en halvutfylt regel truffet ALLE brukere.
        """
        omraade = self._omraade("Halvferdig")
        tom = self.Regel.create(
            {
                "ressurs_id": omraade.id,
                "subjekt_type": "rolle",
                "nivaa": "administrere",
                "regel_type": "tildeling",
                "company_id": self.firma_a.id,
            }
        )
        bruker = self._bruker("Tilfeldig", self.firma_a, rolle=self.rolle_arbeider)

        self.assertFalse(tom.rolle_id, "Forutsetning: regelen har tomt subjekt")
        self.assertFalse(
            tom._gjelder_bruker(bruker), "Regel uten subjekt skal ikke treffe noen"
        )
        self.assertEqual(omraade.effektiv_nivaa(bruker), 0)

    def test_effektiv_nivaa_bruker_innlogget_som_standard(self):
        """Uten `user`-argument skal metoden bruke `self.env.user` — ikke krasje."""
        omraade = self._omraade("Standardbruker")
        self.assertIsInstance(omraade.effektiv_nivaa(), int)

    # ==================================================================
    # 5. ARV OG BRUDD (Novell-modellen) — kjernen i modulen
    # ==================================================================

    def test_arv_fra_forelder_gir_tilgang_paa_barn(self):
        """En regel defineres ÉN gang på forelderen og skal arves nedover.

        Dette er hele salgsargumentet for modulen: «en regel defineres én gang og
        arves nedover treet — den dupliseres ikke per underområde».
        """
        self._krev_hierarki()
        forelder = self._omraade("Hovedomraade")
        barn = self._omraade("Underomraade", forelder=forelder)
        self._regel(forelder, nivaa="skrive", rolle=self.rolle_arbeider)
        bruker = self._bruker("Arver", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(
            barn.effektiv_nivaa(bruker),
            SKRIVE,
            "Tilgang på forelderen skal arves ned til barnet",
        )

    def test_arv_gaar_ikke_oppover(self):
        """🛑 Arven går NEDOVER. Tilgang på et barn gir ikke tilgang på forelderen.

        Går den oppover, gir tilgang til ett underområde tilgang til hele treet.
        """
        self._krev_hierarki()
        forelder = self._omraade("Topp")
        barn = self._omraade("Bunn", forelder=forelder)
        self._regel(barn, nivaa="administrere", rolle=self.rolle_arbeider)
        bruker = self._bruker("Bunnbruker", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(barn.effektiv_nivaa(bruker), ADMINISTRERE)
        self.assertEqual(
            forelder.effektiv_nivaa(bruker),
            0,
            "Tilgang på barnet skal ALDRI lekke opp til forelderen",
        )

    def test_brudd_stopper_arv(self):
        """Novell «Inherited Rights Filter»: et brudd stopper arven fra forelderen."""
        self._krev_hierarki()
        forelder = self._omraade("Aapent")
        barn = self._omraade("Skjermet", forelder=forelder)
        self._regel(forelder, nivaa="administrere", rolle=self.rolle_arbeider)
        self._regel(barn, regel_type="brudd", nivaa="lese", rolle=self.rolle_arbeider)
        bruker = self._bruker("Stoppet", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(forelder.effektiv_nivaa(bruker), ADMINISTRERE)
        self.assertEqual(
            barn.effektiv_nivaa(bruker), 0, "Brudd skal stoppe arven fra forelderen"
        )

    def test_brudd_stopper_bare_for_egen_rolle(self):
        """🛑 Et brudd er subjekt-spesifikt — det skal ikke stenge for alle.

        Bruddet gjelder arbeideren. Lederen, som har sin egen tildeling på
        forelderen, skal fortsatt arve ned.
        """
        self._krev_hierarki()
        forelder = self._omraade("Felles")
        barn = self._omraade("Delvis", forelder=forelder)
        self._regel(forelder, nivaa="skrive", rolle=self.rolle_arbeider)
        self._regel(forelder, nivaa="skrive", rolle=self.rolle_leder)
        self._regel(barn, regel_type="brudd", nivaa="lese", rolle=self.rolle_arbeider)

        arbeider = self._bruker("Stengt Ute", self.firma_a, rolle=self.rolle_arbeider)
        leder = self._bruker("Slipper Inn", self.firma_a, rolle=self.rolle_leder)

        self.assertEqual(barn.effektiv_nivaa(arbeider), 0, "Bruddet gjelder arbeideren")
        self.assertEqual(
            barn.effektiv_nivaa(leder), SKRIVE, "Bruddet skal ikke stenge for lederen"
        )

    def test_tildeling_paa_bruddnoden_gjelder_fortsatt(self):
        """Et brudd stopper ARVEN, men egne tildelinger PÅ noden gjelder.

        Slik gir man «bare lese her, selv om du har administrere over» — som er
        hele poenget med et Inherited Rights Filter.
        """
        self._krev_hierarki()
        forelder = self._omraade("Full")
        barn = self._omraade("Redusert", forelder=forelder)
        self._regel(forelder, nivaa="administrere", rolle=self.rolle_arbeider)
        self._regel(barn, nivaa="lese", rolle=self.rolle_arbeider)
        self._regel(barn, regel_type="brudd", nivaa="lese", rolle=self.rolle_arbeider)
        bruker = self._bruker("Redusert", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(
            barn.effektiv_nivaa(bruker),
            LESE,
            "Egen tildeling på bruddnoden skal gjelde, arven ikke",
        )

    def test_arv_over_tre_nivaaer(self):
        """Arven skal gå hele veien opp forelder-kjeden, ikke bare ett hakk."""
        self._krev_hierarki()
        n1 = self._omraade("Niva1")
        n2 = self._omraade("Niva2", forelder=n1)
        n3 = self._omraade("Niva3", forelder=n2)
        self._regel(n1, nivaa="skrive", rolle=self.rolle_arbeider)
        bruker = self._bruker("Dypt Nede", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(n3.effektiv_nivaa(bruker), SKRIVE, "Arven skal nå tredje nivå")

    def test_brudd_paa_mellomnivaa_skjermer_hele_grenen(self):
        """Et brudd i midten skal skjerme ALT under seg, ikke bare seg selv."""
        self._krev_hierarki()
        n1 = self._omraade("Rot")
        n2 = self._omraade("Sperre", forelder=n1)
        n3 = self._omraade("Under Sperre", forelder=n2)
        self._regel(n1, nivaa="administrere", rolle=self.rolle_arbeider)
        self._regel(n2, regel_type="brudd", nivaa="lese", rolle=self.rolle_arbeider)
        bruker = self._bruker("Sperret", self.firma_a, rolle=self.rolle_arbeider)

        self.assertEqual(n2.effektiv_nivaa(bruker), 0)
        self.assertEqual(
            n3.effektiv_nivaa(bruker),
            0,
            "Brudd på mellomnivå skal skjerme hele grenen under",
        )

    # ==================================================================
    # 6. MODELL-INTEGRITET
    # ==================================================================

    def test_rolle_er_hierarkisk(self):
        """Rollemodellen er `_parent_store` — org-kartet må faktisk henge sammen."""
        self.assertEqual(self.rolle_arbeider.parent_id, self.rolle_leder)
        self.assertIn(self.rolle_arbeider, self.rolle_leder.child_ids)
        self.assertTrue(
            self.rolle_arbeider.parent_path,
            "parent_path må fylles (_parent_store = True)",
        )

    def test_bruker_kobles_til_rolle_begge_veier(self):
        """`bruker_ids` på rollen er motstykket til `fiq_tilgang_rolle_id`."""
        bruker = self._bruker("Koblet", self.firma_a, rolle=self.rolle_arbeider)
        self.assertIn(
            bruker,
            self.rolle_arbeider.bruker_ids,
            "Rollen må kjenne brukeren sin (One2many-motstykket)",
        )

    def test_regel_slettes_med_omraadet(self):
        """`ondelete="cascade"` på ressurs_id: slettes området, dør regelen med det.

        Ellers blir det liggende foreldreløse regler som peker i tomme luften.
        """
        omraade = self._omraade("Midlertidig")
        regel = self._regel(omraade, nivaa="lese", rolle=self.rolle_arbeider)
        self.assertTrue(regel.exists())

        omraade.unlink()
        self.assertFalse(
            regel.exists(), "Regelen skal slettes sammen med området (cascade)"
        )
