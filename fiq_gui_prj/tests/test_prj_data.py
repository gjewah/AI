# -*- coding: utf-8 -*-
"""Tester for Prosjektoversikt-flatens datalag (fiq.gui.prj.data).

Hvorfor de finnes: datalaget ble skrevet 18.07 for å erstatte «Kommer»-stubben.
Første kjøring mot EKTE data avdekket to feil som ingen enhetstest med oppdiktede
verdier ville sett — begge er nå dekket her som regresjonstester.

Lærdom som styrer disse testene: en test som ikke speiler ekte datamønstre beviser
ingenting. Derfor tester vi mot forholdene som faktisk finnes i basen: maler blandet
inn blant prosjekter, og prosjekter uten timeestimat.
"""

from datetime import timedelta

from odoo import fields
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

        # Mønsteret vi aldri vil se: «(00.03)», «(V0.03)», «GUI Prosjekt 01.02»
        #
        # 🔴 FØRSTE UTGAVE VAR FOR GROV — fanget en DATO og feilet bygget:
        #   «Modulen er et tomt «Kommer»-skall, urørt siden 09.07.2026.»
        # `\d{2}\.\d{2}` treffer både «01.02» og «09.07». En test som sperrer
        # enhver dato i en beskrivelse er ubrukelig — og verre: den ville tvunget
        # neste økt til å fjerne den, og dermed mistet vernet helt.
        #
        # Nå kreves KONTEKST som faktisk peker på en økt:
        #   · parentes rundt: «(00.03)» · «(V0.03)»
        #   · eller et øktord foran: «økt 01.02», «GUI Prosjekt 06.74»
        # En bar dato som «09.07.2026» slipper gjennom — den er ikke bokføring.
        okt_monster = re.compile(
            r"\(\s*V?\d{1,2}\.\d{2}\s*\)"
            r"|(?:økt|okt|sesjon|GUI\s+\w+|AI\s+KR|PK)\s+V?\d{1,2}\.\d{2}(?!\.\d)",
            re.IGNORECASE,
        )
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

    # ---------- DATA-BETINGET KRASJ (feilklasse 8) ----------

    def test_oppgaver_over_tid_taaler_oppgave_MED_frist(self):
        """🔴 REGRESJON: krasjet fiqas Staging 21.07 kl. 22:58 — blank skjerm.

            TypeError: can't compare datetime.datetime to datetime.date
            fiq_gui_prj_data.py:243  →  if frist < i_dag

        `date_deadline` er **Datetime** i Odoo 19 (verifisert i kilden:
        project/models/project_task.py:183, og i `ir_model_fields` = «datetime»),
        mens `i_dag` er en **Date**. Sammenligningen er ulovlig i Python.

        🔑 HVORFOR DEN GLAPP GJENNOM 42 GRØNNE TESTER:
        koden returnerte på «if not frist» når ingen oppgave hadde frist satt. På en
        tynn base ble sammenligningen ALDRI nådd. Etter rebuild fra Production fantes
        ekte frister — og første kall smalt. Testen var grønn fordi den aldri kom dit.

        Denne testen OPPRETTER en oppgave med frist, så kodeveien tvinges gjennom
        uansett hvordan basen ser ut. En test som bare leser eksisterende data kan
        ikke bevise fravær av data-betingede krasj.
        """
        from datetime import timedelta
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        oppgaver = self.env["project.task"].create([
            {"name": "TEST frist passert", "project_id": prosjekt.id,
             "date_deadline": fields.Datetime.to_datetime(i_dag - timedelta(days=3))},
            {"name": "TEST frist om 3 dager", "project_id": prosjekt.id,
             "date_deadline": fields.Datetime.to_datetime(i_dag + timedelta(days=3))},
            {"name": "TEST frist langt fram", "project_id": prosjekt.id,
             "date_deadline": fields.Datetime.to_datetime(i_dag + timedelta(days=60))},
        ])

        # Selve kallet — dette er det som ga 500 og blank skjerm.
        res = self.Data.get_oppgaver_over_tid(antall=7)

        self.assertIn("oppgaver", res)
        self.assertIn("kpi", res)

        # Statusen må også være RIKTIG, ikke bare fri for krasj.
        per_id = {r["id"]: r for r in res["oppgaver"]}
        forventet = ["krit", "folg", "rute"]
        for opg, vent in zip(oppgaver, forventet):
            r = per_id.get(opg.id)
            if r:
                self.assertEqual(
                    r["tid_status"], vent,
                    "«%s» fikk status «%s», forventet «%s»" % (opg.name, r["tid_status"], vent),
                )
                # Frist skal være en ren datostreng, ikke et tidsstempel.
                self.assertRegex(
                    str(r["frist"]), r"^\d{4}-\d{2}-\d{2}$",
                    "Frist skal være dato uten klokkeslett, fikk %r" % r["frist"],
                )

    def test_frist_sent_paa_dagen_forsvinner_ikke(self):
        """🔴 REGRESJON: en frist kl. 15:00 skal ikke falle ut av siste kolonne.

        `date_deadline` er Datetime. Sender vi et rent `date`-objekt inn i domenet,
        tolker Odoo det som MIDNATT — og alt senere den dagen forsvinner STILLE.
        Ingen feilmelding, ingen tom liste. Bare en oppgave som ikke er der.

        Verifisert mot basen 22.07: `<= date(...)` gir samme treff som
        `<= datetime(..., 00:00:00)`. I dag er alle frister på midnatt, så feilen er
        usynlig. Første gang noen setter klokkeslett, biter den.

        Samme klasse som Kommunikasjons fredags-frister som forsvant fra ukesplanen.
        Meldt av KR 22.07 før det rakk å bli et ekte tap her.
        """
        from datetime import timedelta
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        # Siste dag i et 7-ukers vindu som starter denne uka
        start = i_dag - timedelta(days=i_dag.weekday())
        siste_dag = start + timedelta(weeks=7) - timedelta(days=1)

        sen = self.env["project.task"].create({
            "name": "TEST frist kl 15 siste dag",
            "project_id": prosjekt.id,
            # 15:00 samme dag — ville falt utenfor med midnatt-grense
            "date_deadline": fields.Datetime.to_datetime(
                "%s 15:00:00" % fields.Date.to_string(siste_dag)
            ),
        })

        res = self.Data.get_oppgaver_over_tid(antall=7)
        ider = {r["id"] for r in res["oppgaver"]}
        self.assertIn(
            sen.id, ider,
            "Oppgave med frist kl. 15:00 på siste dag i vinduet forsvant. "
            "Domenegrensen kutter trolig ved midnatt — bruk datetime.max.time().",
        )

    def test_gantt_returnerer_bare_TEGNBARE_oppgaver(self):
        """🔴 MÅLT 22.07: 379 av 400 oppgaver kunne ikke tegnes.

        Det gamle domenet hadde `("date_deadline", "=", False)` som eget OR-ledd —
        altså «ta med alt uten frist». Resultatet var 379 rader uten søyle: Gantt-en
        så nesten tom ut, og KPI-ene summerte til 21 av 400.

        🔑 Feilen var USYNLIG i alle tidligere tester. Metoden svarte 200, returnerte
        400 rader, ingen exception. Den var «grønn» på hvert eneste mål vi hadde —
        og likevel ubrukelig, fordi 95 % av radene ikke kunne tegnes.

        En tidslinje som viser rader uten tid er ikke en tidslinje.
        """
        res = self.Data.get_oppgaver_over_tid(antall=7)
        if not res["oppgaver"]:
            self.skipTest("Ingen daterte oppgaver i vinduet")

        udaterte = [o for o in res["oppgaver"] if not o["fra"] and not o["frist"]]
        self.assertFalse(
            udaterte,
            "%d av %d oppgaver mangler BÅDE start og frist og kan ikke tegnes. "
            "Første: «%s». Udaterte oppgaver hører hjemme i Liste/Kanban, ikke i Gantt."
            % (len(udaterte), len(res["oppgaver"]),
               udaterte[0]["navn"] if udaterte else ""),
        )

    # ---------- SJEKKLISTE-PANELET ----------

    def test_sjekklister_taaler_oppgave_uten_lister(self):
        """En oppgave uten sjekklister skal gi tom liste, ikke krasj.

        Basen har 0 sjekklister i dag (målt 19.07) — motoren er ubrukt i praksis.
        Flaten må tåle det uten å se ødelagt ut.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")
        t = self.env["project.task"].create({
            "name": "TEST uten sjekkliste", "project_id": prosjekt.id,
        })
        res = self.Data.get_sjekklister(t.id)
        self.assertTrue(res["tilgjengelig"])
        self.assertEqual(res["lister"], [])
        self.assertEqual(res["oppgave"]["id"], t.id)

    def test_sjekklister_viser_krav_og_sperre(self):
        """🔑 Panelet må vise motorens sperre, ikke finne opp sin egen.

        Kravene er UAVHENGIGE (Gjermund 16.07): dok / foto / signatur. Et punkt kan
        ikke kvitteres før ALLE påslåtte krav er levert — det håndheves av
        `@api.constrains` i motoren, ikke av flaten.

        Denne testen oppretter tilstanden den verner mot (port 6): en liste med ett
        punkt som krever dokument, uten at dokumentet finnes.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")
        t = self.env["project.task"].create({
            "name": "TEST med sjekkliste", "project_id": prosjekt.id,
        })
        s = self.env["fiq.sjekkliste"].create({
            "name": "Testliste", "task_id": t.id,
            "punkt_ids": [(0, 0, {"name": "Krever dok", "krav_dok": True})],
        })

        res = self.Data.get_sjekklister(t.id)
        self.assertEqual(len(res["lister"]), 1, "Sjekklista kom ikke med")
        liste = res["lister"][0]
        self.assertEqual(liste["antall"], 1)
        self.assertEqual(liste["fremdrift"], 0.0)

        p = liste["punkter"][0]
        self.assertIn("dok", p["krav"], "Kravet «dok» mangler i det flaten viser")
        self.assertFalse(
            p["kan_kvitteres"],
            "Punktet krever dokument som ikke finnes — sperren skal være synlig i flaten",
        )
        self.assertTrue(p["mangler"], "Brukeren må få vite HVA som mangler, ikke bare at det er sperret")

    def test_sjekklister_respekterer_firma_scope(self):
        """Oppgave utenfor sesjonens firmaer skal ikke gi data."""
        res = self.Data.get_sjekklister(oppgave_id=999999999)
        self.assertFalse(res["oppgave"], "Ukjent oppgave skal ikke gi innhold")

    def _prosjekt_domene_for_test(self):
        """Prosjekt vi trygt kan henge testoppgaver på."""
        d = [("company_id", "in", self.env.companies.ids or [self.env.company.id])]
        if "is_template" in self.Project._fields:
            d += [("is_template", "=", False)]
        return d

    # ---------- RISIKO-DOMMEN (krav 7) ----------
    #
    # 🔑 Fasitens fire eksempler ER testdataene. AI KR/AI PK 23.07: «Dere har
    # tallet. Fasiten vil ha dommen.» Testene under sjekker at vi feller den
    # samme dommen som fasiten viser — ikke bare at metoden svarer noe.
    #
    # 📌 Alle regner på egen tilstand (kanon 4i): ingen påstand her avhenger av
    # hva som tilfeldigvis står i basen. En test som leser Dev-demodata og
    # konkluderer om FIQ er nettopp feilen vi ble tatt for i dag.

    def test_risiko_i_balanse_naar_forbruk_foelger_fremdrift(self):
        """Fasiten: «26_042 Kabelgata · 62 % brukt / 62 % fremdrift → i balanse»."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=62.0, budsjett=100.0, fremdrift=62.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(
            dom, "i_balanse",
            "62 % brukt av 62 % ferdig er sunt — det skal ikke merkes som risiko",
        )

    def test_risiko_tett_budsjett_naar_forbruk_loeper_fra_fremdriften(self):
        """Pengene brukes fortere enn arbeidet blir gjort.

        🔑 Dette er hele poenget med dommen: INGEN grense er passert (62 < 100),
        så både `budsjett_status` og et rent forbrukstall sier «innenfor». Odoo
        sier ingenting. Men 62 % brukt på 20 % arbeid er på vei mot sprekk, og
        det er nettopp det Gjermund skal få vite FØR det smeller.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=62.0, budsjett=100.0, fremdrift=20.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(
            dom, "tett_budsjett",
            "62 % brukt på 20 % fremdrift skal varsles, ikke passere som «innenfor»",
        )

    def test_risiko_frist_i_dag_slaar_sunt_budsjett(self):
        """Fasiten: «24_055 Oscarsgate · tilbud avgjøres i dag kl 15 → avgjøres».

        Budsjettet er helt sunt. Dommen skal likevel være «avgjøres» — en frist
        i dag tåler ikke å vente til i morgen, uansett hvor bra økonomien er.
        Det er derfor risiko er en EGEN akse og ikke en omskriving av budsjett.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=10.0, budsjett=100.0, fremdrift=10.0,
            naermeste_frist=i_dag, i_dag=i_dag,
        )
        self.assertEqual(dom, "avgjores", "Frist i dag skal slå gjennom alt annet")

    def test_risiko_passert_frist_gir_avgjores(self):
        """En frist som er passert er ikke «tett tid» — den er forbi."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=1.0, budsjett=100.0, fremdrift=90.0,
            naermeste_frist=i_dag - timedelta(days=5), i_dag=i_dag,
        )
        self.assertEqual(dom, "avgjores", "Passert frist må aldri se ut som i balanse")

    def test_risiko_over_budsjett_er_alltid_roedt(self):
        """Brukt mer enn budsjettet: rødt uansett fremdrift."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=159.3, budsjett=1.0, fremdrift=100.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(dom, "over_budsjett", "15 931 % forbruk skal aldri passere")

    def test_risiko_ferdig_prosjekt_er_ikke_risiko(self):
        """Alt ferdig = ingen dom å felle, uansett hvor galt det gikk underveis."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=999.0, budsjett=1.0, fremdrift=100.0,
            naermeste_frist=i_dag - timedelta(days=30), i_dag=i_dag, ferdig=True,
        )
        self.assertEqual(dom, "ferdig", "Et avsluttet prosjekt er historie, ikke risiko")

    def test_risiko_hvorfor_forklarer_dommen_i_klartekst(self):
        """🔑 Et merke uten begrunnelse er bare et nytt tall å tolke.

        Fasiten viser ALDRI merket alene: «62 % brukt / 62 % fremdrift»,
        «EM-frist i dag». Gjermund skal kunne lese linja og vite hva han skal
        gjøre — ikke måtte åpne prosjektet for å finne ut hvorfor det er rødt.
        """
        i_dag = fields.Date.today()
        tekst = self.Data._risiko_hvorfor(
            fort=62.0, budsjett=100.0, fremdrift=20.0,
            naermeste_frist=i_dag, i_dag=i_dag,
        )
        self.assertIn("frist i dag", tekst.lower(), "Fristen må stå i klartekst")
        self.assertIn("%", tekst, "Forbruk mot fremdrift må vises som tall")

    def test_risiko_hvorfor_er_aldri_tom(self):
        """Uten frist og budsjett skal linja forklare seg, ikke stå tom.

        En tom celle ser ut som manglende data. «ingen frist eller budsjett satt»
        er et svar — og det er ofte selve funnet.
        """
        tekst = self.Data._risiko_hvorfor(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=None, i_dag=fields.Date.today(),
        )
        self.assertTrue(tekst.strip(), "Begrunnelsen skal aldri være tom")

    def test_prosjektoversikt_har_risiko_paa_hver_rad(self):
        """Dommen skal FAKTISK nå flaten — ikke bare finnes som metode.

        🔴 Denne testen finnes fordi jeg 22.07 bygde sjekkliste-datalaget i
        1.21.0 og aldri koblet det til flaten. AI KRs sidemannskontroll fant
        det: 0 treff i prj.xml/prj.js. «Metoden finnes» og «flaten viser det»
        er to forskjellige påstander.
        """
        res = self.Data.get_prosjektoversikt(grense=20)
        if not res["prosjekter"]:
            self.skipTest("Ingen prosjekter å teste mot")
        for p in res["prosjekter"]:
            self.assertIn("risiko", p, "Hver prosjektrad må bære en risiko-dom")
            self.assertIn("risiko_hvorfor", p, "Dommen må ha en begrunnelse")
            self.assertTrue(
                str(p["risiko_hvorfor"]).strip(),
                "Begrunnelsen var tom for %s" % p["navn"],
            )
