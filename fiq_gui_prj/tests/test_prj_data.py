# -*- coding: utf-8 -*-
"""Tester for Prosjektoversikt-flatens datalag (fiq.gui.prj.data).

Hvorfor de finnes: datalaget ble skrevet 18.07 for å erstatte «Kommer»-stubben.
Første kjøring mot EKTE data avdekket to feil som ingen enhetstest med oppdiktede
verdier ville sett — begge er nå dekket her som regresjonstester.

Lærdom som styrer disse testene: en test som ikke speiler ekte datamønstre beviser
ingenting. Derfor tester vi mot forholdene som faktisk finnes i basen: maler blandet
inn blant prosjekter, og prosjekter uten timeestimat.
"""

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_prj")
class TestPrjData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.prj.data"]
        cls.Project = cls.env["project.project"]

    # ---------- MALER SKAL ALDRI VISES ----------

    def test_maler_ekskluderes(self):
        """🔴 REGRESJON: maler fylte hele førstesiden.

        Ekte funn 18.07: basen hadde 150 prosjekter, hvorav 12 maler (0.90-serien).
        Uten filter var ALLE fem øverste treff «(TEMPLATE)» — ekte prosjekter ble
        skjøvet ut av visningen. AI KTRL-kontrakten: «is_template = True ekskluderes
        automatisk — 0.90-serien er MALER, rør dem aldri.»
        """
        if "is_template" not in self.Project._fields:
            self.skipTest("is_template finnes ikke i denne Odoo-versjonen")

        res = self.Data.get_prosjektoversikt(grense=200)
        viste_ider = [p["id"] for p in res["prosjekter"]]
        if not viste_ider:
            self.skipTest("Ingen prosjekter å teste mot")

        maler = self.Project.search([("id", "in", viste_ider), ("is_template", "=", True)])
        self.assertFalse(
            maler,
            "Maler skal ALDRI vises i Prosjektoversikt, men disse kom med: %s"
            % maler.mapped("name"),
        )

    # ---------- FREMDRIFT: ÆRLIG OM KILDEN ----------

    def test_fremdrift_uten_timeestimat_bruker_ikke_timer(self):
        """🔴 REGRESJON: «0,0 % (timer)» på et prosjekt med 66 oppgaver.

        Ekte funn 18.07: de fleste prosjekter har allocated_hours = 0. Da er
        «beregnet fra timer» meningsløst og direkte villedende — det ser ut som
        en datafeil. Uten timeestimat SKAL kilden være oppgaveandel («anslag»)
        eller «ingen», aldri «timer».
        """
        res = self.Data.get_prosjektoversikt(grense=200)
        for p in res["prosjekter"]:
            if not p["budsjett_timer"]:
                self.assertNotEqual(
                    p["fremdrift_kilde"], "timer",
                    "«%s» har ingen estimerte timer, men oppgir «timer» som "
                    "fremdriftskilde — det er villedende." % p["navn"],
                )

    def test_overforbruk_vises_ekte_og_kappes_aldri(self):
        """🔴 REGRESJON: kappingen skjulte et 22x overforbruk.

        Denne testen ERSTATTER `test_fremdrift_er_alltid_mellom_0_og_100`, som
        asserterte det motsatte: at fremdrift aldri oversteg 100, «fordi stripa
        ikke tåler over 100». Den testen SEMENTERTE feilen i stedet for å avsløre
        den — koden gjorde `min(100.0, ...)`, og testen sa at det var riktig.

        Ekte tilfelle fra basen: 215,9 timer ført mot budsjett 10 ble vist som
        «100 % grønn». Et 2159 % overforbruk — nettopp det varselet den som styrer
        økonomien MÅ se — var usynlig. Det er ikke en visningsfeil; det er å skjule
        et varsku.

        Kravspek batch 15: blå = innenfor budsjett · RØD = OVER budsjett.
        Stripa klippes visuelt i SCSS (width kan ikke være 2159 %), men TALLET
        og STATUSEN skal alltid være ærlige.

        Skrevet slik at `min(100.0, ...)` ville FEILET den.
        """
        res = self.Data.get_prosjektoversikt(grense=200)
        for p in res["prosjekter"]:
            fort = p["forte_timer"]
            budsjett = p["budsjett_timer"]
            pst = p["forbruk_prosent"]

            self.assertGreaterEqual(pst, 0.0, p["navn"])

            if budsjett > 0 and fort > budsjett:
                # Over budsjett: prosenten SKAL passere 100 og statusen SKAL være «over».
                self.assertGreater(
                    pst, 100.0,
                    "«%s» har ført %s t mot budsjett %s t — det er over budsjett, "
                    "men forbruket vises som %s %%. Kappes tallet, skjuler flaten "
                    "overforbruket." % (p["navn"], fort, budsjett, pst),
                )
                self.assertEqual(
                    p["budsjett_status"], "over",
                    "«%s» er over budsjett (%s t mot %s t), men status er «%s» — "
                    "skal være «over» (rød)." % (p["navn"], fort, budsjett, p["budsjett_status"]),
                )

    def test_forbruk_regnes_uten_kapping(self):
        """Regnestykket direkte: 215,9 timer mot budsjett 10 = 2159 %, ikke 100.

        Uavhengig av hva som ligger i basen — dette er tallet fra det ekte funnet,
        og det skal aldri kappes igjen.
        """
        self.assertEqual(self.Data._forbruk_prosent(215.9, 10.0), 2159.0)
        self.assertEqual(self.Data._forbruk_prosent(50.0, 100.0), 50.0)
        # Uten budsjett er en prosentandel meningsløs — ikke null, men «ingen».
        self.assertEqual(self.Data._forbruk_prosent(80.0, 0.0), 0.0)

    def test_budsjett_status_er_rod_ved_overforbruk(self):
        """Fargeaksen i batch 15: blå innenfor · rød over · grønn ferdig.

        🔴 Ferdig SLÅR IKKE UT over rødt: en ferdig aktivitet som brukte 3x
        budsjettet er ikke en suksess å farge grønn — det er erfaringen neste
        kalkyle skal bygge på.
        """
        self.assertEqual(self.Data._budsjett_status(5.0, 10.0, False), "innenfor")
        self.assertEqual(self.Data._budsjett_status(15.0, 10.0, False), "over")
        self.assertEqual(self.Data._budsjett_status(8.0, 10.0, True), "ferdig")
        self.assertEqual(self.Data._budsjett_status(30.0, 10.0, True), "over")
        self.assertEqual(self.Data._budsjett_status(0.0, 0.0, False), "plan")

    def test_fremdrift_kilde_er_alltid_oppgitt(self):
        """Brukeren skal alltid kunne se om tallet er fasit eller anslag."""
        res = self.Data.get_prosjektoversikt(grense=50)
        for p in res["prosjekter"]:
            self.assertIn(p["fremdrift_kilde"], ("timer", "oppgaver", "ingen"), p["navn"])

    # ---------- TENANT-ISOLASJON ----------

    def test_firma_id_kan_kun_snevre_inn(self):
        """Et firma sesjonen IKKE har, skal aldri utvide innsynet.

        Sendes en ukjent/ulovlig firma_id, faller vi tilbake til sesjonens egne
        firmaer — aldri til «alle». company_id kommer fra sesjonen, aldri fra klient.
        """
        res = self.Data.get_prosjektoversikt(firma_id=999999, grense=50)
        tillatte = set(self.env.companies.ids or [self.env.company.id])
        for p in res["prosjekter"]:
            self.assertIn(
                p["firma_id"], tillatte,
                "Prosjekt «%s» tilhører firma utenfor sesjonens scope" % p["navn"],
            )

    def test_firmaliste_er_sesjonens_firmaer(self):
        """Firma-velgeren skal kun tilby firmaer brukeren faktisk har."""
        res = self.Data.get_prosjektoversikt(grense=1)
        tillatte = set(self.env.companies.ids or [self.env.company.id])
        self.assertEqual(set(f["id"] for f in res["firmaer"]), tillatte)

    # ---------- DRILL: OPPGAVER ----------

    def test_get_oppgaver_returnerer_stabile_og_dynamiske_nummer(self):
        """Oppgavenr (code) er stabilt, disposisjonsnr (WBS) er dynamisk — begge med."""
        res = self.Data.get_prosjektoversikt(grense=50)
        med_oppgaver = [p for p in res["prosjekter"] if p["antall_oppgaver"]]
        if not med_oppgaver:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        drill = self.Data.get_oppgaver(med_oppgaver[0]["id"])
        self.assertTrue(drill["oppgaver"], "Prosjektet oppga oppgaver, men drill ga ingen")
        for t in drill["oppgaver"]:
            self.assertIn("oppgavenr", t)
            self.assertIn("wbs", t)
            self.assertIsInstance(t["er_ai"], bool)

    def test_oppgavetelling_stemmer_mellom_nivaaene(self):
        """Tallet i oversikten må stemme med det drill faktisk viser.

        Ellers ser brukeren «5 oppgaver» og får opp 3 — den slags undergraver
        tilliten til hele flaten.
        """
        res = self.Data.get_prosjektoversikt(grense=20)
        med_oppgaver = [p for p in res["prosjekter"] if p["antall_oppgaver"]]
        if not med_oppgaver:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        p = med_oppgaver[0]
        drill = self.Data.get_oppgaver(p["id"])
        self.assertEqual(
            len(drill["oppgaver"]), p["antall_oppgaver"],
            "«%s»: oversikten sier %d oppgaver, drill viser %d"
            % (p["navn"], p["antall_oppgaver"], len(drill["oppgaver"])),
        )

    # ---------- WBS-TREET (kravspek batch 15) ----------

    def _et_tre(self, minst_noder=1):
        """Hent WBS-treet for et prosjekt som faktisk har oppgaver."""
        res = self.Data.get_prosjektoversikt(grense=50)
        for p in sorted(res["prosjekter"], key=lambda x: -x["antall_oppgaver"]):
            if p["antall_oppgaver"] >= minst_noder:
                return self.Data.get_wbs_tre(p["id"])
        return None

    def test_wbs_tre_har_noder_naar_prosjektet_har_oppgaver(self):
        """🔴 «Installert + grønt» betyr ikke «flaten viser noe».

        Fire ganger i juli var alt grønt mens flaten var tom. Denne testen krever
        at treet faktisk inneholder noder når prosjektet har oppgaver — den ville
        fanget «Kommer»-stubben.
        """
        tre = self._et_tre()
        if not tre:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")
        self.assertTrue(
            tre["noder"],
            "Prosjektet «%s» har %d oppgaver, men WBS-treet er tomt."
            % (tre["prosjekt"]["navn"], tre["antall_noder"]),
        )

    def test_wbs_tre_teller_alle_oppgaver_inkludert_underoppgaver(self):
        """Ingen oppgave skal falle ut av treet.

        En oppgave hvis forelder ligger utenfor domenet må behandles som rot —
        ellers blir den usynlig OG timene forsvinner fra rollupen. Summen av
        noder i treet skal alltid være lik antall oppgaver i prosjektet.
        """
        tre = self._et_tre()
        if not tre:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        def tell(noder):
            return sum(1 + tell(n["barn"]) for n in noder)

        self.assertEqual(
            tell(tre["noder"]), tre["antall_noder"],
            "«%s»: %d oppgaver i basen, men %d noder i treet — noe falt ut."
            % (tre["prosjekt"]["navn"], tre["antall_noder"], tell(tre["noder"])),
        )

    def test_wbs_rollup_summerer_barnas_timer(self):
        """En forelders timer = egne timer + alle barnas.

        Odoo lar deg føre timer direkte på en forelder selv om den har barn,
        så begge deler må med. Uten dette forsvinner timer ført på en fase.
        """
        tre = self._et_tre()
        if not tre:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        def sjekk(node):
            if node["barn"]:
                ventet = node["egne_timer"] + sum(b["forte_timer"] for b in node["barn"])
                self.assertAlmostEqual(
                    node["forte_timer"], round(ventet, 1), places=1,
                    msg="«%s»: rollup gir %s t, men egne (%s) + barnas (%s) = %s"
                    % (node["navn"], node["forte_timer"], node["egne_timer"],
                       sum(b["forte_timer"] for b in node["barn"]), ventet),
                )
            for b in node["barn"]:
                sjekk(b)

        for n in tre["noder"]:
            sjekk(n)

    def test_wbs_rod_status_arves_oppover(self):
        """Verste status vinner: ett rødt barn gjør forelderen rød.

        Ellers ville et overforbrukt rom druknet i et stort prosjekt som
        «ser fint ut» på toppnivå — akkurat den skjulingen vi rettet.
        """
        tre = self._et_tre()
        if not tre:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        def sjekk(node):
            if any(b["budsjett_status"] == "over" for b in node["barn"]):
                self.assertEqual(
                    node["budsjett_status"], "over",
                    "«%s» har et barn over budsjett, men står som «%s» — "
                    "overforbruk skal aldri skjules bak en forelder."
                    % (node["navn"], node["budsjett_status"]),
                )
            for b in node["barn"]:
                sjekk(b)

        for n in tre["noder"]:
            sjekk(n)

    def test_wbs_tre_respekterer_tenant_isolasjon(self):
        """Treet skal aldri vise oppgaver utenfor sesjonens firmaer."""
        tre = self._et_tre()
        if not tre:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        tillatte = set(self.env.companies.ids or [self.env.company.id])
        ider = []

        def samle(noder):
            for n in noder:
                ider.append(n["id"])
                samle(n["barn"])

        samle(tre["noder"])
        if ider:
            firmaer = set(self.env["project.task"].browse(ider).mapped("company_id").ids)
            self.assertTrue(
                firmaer.issubset(tillatte | {False}),
                "WBS-treet viser oppgaver fra firmaer utenfor sesjonen: %s" % (firmaer - tillatte),
            )

    # ---------- AI-ARBEID SOM PROSJEKT (Gjermund-direktiv 20.07) ----------

    def test_ai_arbeid_taaler_at_ai_kr_mangler(self):
        """Flaten skal ikke falle om `fiq_gui_ai_kr` ikke er installert.

        En manglende nabomodul er ikke en feil i denne flaten. Uten dette ville
        PRJ-flaten blitt avhengig av at AI KR alltid er der — og en flate som tar
        ned en annen flate er nøyaktig det savepoint-arbeidet i KR skal hindre.
        """
        res = self.Data.get_ai_arbeid()
        self.assertIn("tilgjengelig", res)
        self.assertIn("spor", res)
        self.assertIsInstance(res["spor"], list)
        if not res["tilgjengelig"]:
            self.assertEqual(res["spor"], [], "Utilgjengelig skal gi tom liste, ikke halve data")

    def test_ai_arbeid_lekker_aldri_oktnummer(self):
        """🔴 KJERNEN I DIREKTIVET: Gjermund skal ALDRI se «01.02» i denne flaten.

        Ordrett 20.07: «pktsystemet til Claude kan dra et vist mørk plass… det har
        kostet dager med ekstra arbide og over 100 timer.»

        Øktnummeret er Claudes bokføring. Det flytter seg mens arbeidet står stille,
        så en referanse skrevet i dag peker på en død økt i morgen. Denne testen
        ville feilet om noen senere la øktnummer inn i visningen «bare som info».
        """
        import re
        res = self.Data.get_ai_arbeid()
        if not res["tilgjengelig"] or not res["spor"]:
            self.skipTest("fiq_gui_ai_kr ikke installert, eller ingen spor å teste mot")

        # Mønsteret vi aldri vil se: «00.03», «01.02», «(V0.03)», «06.74»
        okt_monster = re.compile(r"\b\(?V?\d{2}\.\d{2}\)?\b")
        for s in res["spor"]:
            for felt in ("navn", "beskrivelse", "kode"):
                verdi = str(s.get(felt) or "")
                self.assertIsNone(
                    okt_monster.search(verdi),
                    "Øktnummer lekket inn i «%s» på sporet «%s»: %r. "
                    "Gjermund skal se ARBEID, ikke Claudes bokføring."
                    % (felt, s.get("navn"), verdi),
                )
            # `aktivitet` er et TALL (hvor mye som skjer) — aldri et øktnummer.
            self.assertIsInstance(s["aktivitet"], int, s.get("navn"))

    def test_ai_arbeid_sier_aerlig_hva_som_er_ukoblet(self):
        """Et spor uten prosjekt skal vises ÆRLIG som ukoblet.

        Alternativet — å skjule ukoblede spor — ville gitt et bilde som ser komplett
        ut mens noe mangler. Samme prinsipp som «1 uten samtykke skjult» i presence.
        AI KR kobler kun på eksakt navnetreff og oppretter ALDRI prosjekter (kanon),
        så ukoblede spor er en normal og forventet tilstand.
        """
        res = self.Data.get_ai_arbeid()
        if not res["tilgjengelig"]:
            self.skipTest("fiq_gui_ai_kr ikke installert")

        for s in res["spor"]:
            self.assertEqual(
                s["koblet"], bool(s["project_id"]),
                "«%s»: «koblet» må speile om project_id faktisk finnes" % s.get("navn"),
            )
        self.assertEqual(
            res["antall_koblet"], sum(1 for s in res["spor"] if s["koblet"]),
            "Tellingen av koblede spor stemmer ikke med listen",
        )

    def test_ai_arbeid_respekterer_firma_scope(self):
        """Firma-valget kan kun SNEVRE INN — aldri utvide. Samme regel som resten."""
        res = self.Data.get_ai_arbeid(firma_id=999999)
        self.assertIn("valgt_firma", res)
        self.assertFalse(
            res["valgt_firma"],
            "Et firma sesjonen ikke har, skal falle tilbake til sesjonens scope — ikke aksepteres",
        )
