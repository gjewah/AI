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


@tagged("post_install", "-at_install", "fiq", "fiq_prj")
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

        maler = self.Project.search(
            [("id", "in", viste_ider), ("is_template", "=", True)]
        )
        self.assertFalse(
            maler,
            "Maler skal ALDRI vises i Prosjektoversikt, men disse kom med: {}".format(
                maler.mapped("name")
            ),
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
                    p["fremdrift_kilde"],
                    "timer",
                    "«{}» har ingen estimerte timer, men oppgir «timer» som "
                    "fremdriftskilde — det er villedende.".format(p["navn"]),
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
                    pst,
                    100.0,
                    "«{}» har ført {} t mot budsjett {} t — det er over budsjett, "
                    "men forbruket vises som {} %. Kappes tallet, skjuler flaten "
                    "overforbruket.".format(p["navn"], fort, budsjett, pst),
                )
                self.assertEqual(
                    p["budsjett_status"],
                    "over",
                    "«{}» er over budsjett ({} t mot {} t), men status er «{}» — "
                    "skal være «over» (rød).".format(
                        p["navn"], fort, budsjett, p["budsjett_status"]
                    ),
                )

    # 📌 FLYTTET til tests/test_prj_data_lag.py (23.07, datalags-delingen):
    #    test_forbruk_regnes_uten_kapping · test_budsjett_status_er_rod_ved_overforbruk
    #    Begge regner på oppdiktede tall og rører aldri flaten. Testen over
    #    (test_overforbruk_vises_ekte_og_kappes_aldri) blir HER — den krever at
    #    de ekte radene flaten viser er ærlige, som er flatens kontrakt.

    def test_fremdrift_kilde_er_alltid_oppgitt(self):
        """Brukeren skal alltid kunne se om tallet er fasit eller anslag."""
        res = self.Data.get_prosjektoversikt(grense=50)
        for p in res["prosjekter"]:
            self.assertIn(
                p["fremdrift_kilde"], ("timer", "oppgaver", "ingen"), p["navn"]
            )

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
                p["firma_id"],
                tillatte,
                "Prosjekt «{}» tilhører firma utenfor sesjonens scope".format(
                    p["navn"]
                ),
            )

    def test_firmaliste_er_sesjonens_firmaer(self):
        """Firma-velgeren skal kun tilby firmaer brukeren faktisk har."""
        res = self.Data.get_prosjektoversikt(grense=1)
        tillatte = set(self.env.companies.ids or [self.env.company.id])
        self.assertEqual({f["id"] for f in res["firmaer"]}, tillatte)

    # ---------- DRILL: OPPGAVER ----------

    def test_get_oppgaver_returnerer_stabile_og_dynamiske_nummer(self):
        """Oppgavenr (code) er stabilt, disposisjonsnr (WBS) er dynamisk — begge med."""
        res = self.Data.get_prosjektoversikt(grense=50)
        med_oppgaver = [p for p in res["prosjekter"] if p["antall_oppgaver"]]
        if not med_oppgaver:
            self.skipTest("Ingen prosjekter med oppgaver å teste mot")

        drill = self.Data.get_oppgaver(med_oppgaver[0]["id"])
        self.assertTrue(
            drill["oppgaver"], "Prosjektet oppga oppgaver, men drill ga ingen"
        )
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
            len(drill["oppgaver"]),
            p["antall_oppgaver"],
            "«{}»: oversikten sier {} oppgaver, drill viser {}".format(
                p["navn"], p["antall_oppgaver"], len(drill["oppgaver"])
            ),
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
            "Prosjektet «{}» har {} oppgaver, men WBS-treet er tomt.".format(
                tre["prosjekt"]["navn"], tre["antall_noder"]
            ),
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
            tell(tre["noder"]),
            tre["antall_noder"],
            "«{}»: {} oppgaver i basen, men {} noder i treet — noe falt ut.".format(
                tre["prosjekt"]["navn"], tre["antall_noder"], tell(tre["noder"])
            ),
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
                ventet = node["egne_timer"] + sum(
                    b["forte_timer"] for b in node["barn"]
                )
                self.assertAlmostEqual(
                    node["forte_timer"],
                    round(ventet, 1),
                    places=1,
                    msg="«{}»: rollup gir {} t, men egne ({}) + barnas ({}) = {}".format(
                        node["navn"],
                        node["forte_timer"],
                        node["egne_timer"],
                        sum(b["forte_timer"] for b in node["barn"]),
                        ventet,
                    ),
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
                    node["budsjett_status"],
                    "over",
                    "«{}» har et barn over budsjett, men står som «{}» — "
                    "overforbruk skal aldri skjules bak en forelder.".format(
                        node["navn"], node["budsjett_status"]
                    ),
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
            firmaer = set(
                self.env["project.task"].browse(ider).mapped("company_id").ids
            )
            self.assertTrue(
                firmaer.issubset(tillatte | {False}),
                f"WBS-treet viser oppgaver fra firmaer utenfor sesjonen: {firmaer - tillatte}",
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
            self.assertEqual(
                res["spor"], [], "Utilgjengelig skal gi tom liste, ikke halve data"
            )

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
                    "Øktnummer lekket inn i «{}» på sporet «{}»: {!r}. "
                    "Gjermund skal se ARBEID, ikke Claudes bokføring.".format(
                        felt, s.get("navn"), verdi
                    ),
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
                s["koblet"],
                bool(s["project_id"]),
                "«{}»: «koblet» må speile om project_id faktisk finnes".format(
                    s.get("navn")
                ),
            )
        self.assertEqual(
            res["antall_koblet"],
            sum(1 for s in res["spor"] if s["koblet"]),
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
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        oppgaver = self.env["project.task"].create(
            [
                {
                    "name": "TEST frist passert",
                    "project_id": prosjekt.id,
                    "date_deadline": fields.Datetime.to_datetime(
                        i_dag - timedelta(days=3)
                    ),
                },
                {
                    "name": "TEST frist om 3 dager",
                    "project_id": prosjekt.id,
                    "date_deadline": fields.Datetime.to_datetime(
                        i_dag + timedelta(days=3)
                    ),
                },
                {
                    "name": "TEST frist langt fram",
                    "project_id": prosjekt.id,
                    "date_deadline": fields.Datetime.to_datetime(
                        i_dag + timedelta(days=60)
                    ),
                },
            ]
        )

        # Selve kallet — dette er det som ga 500 og blank skjerm.
        res = self.Data.get_oppgaver_over_tid(antall=7)

        self.assertIn("oppgaver", res)
        self.assertIn("kpi", res)

        # Statusen må også være RIKTIG, ikke bare fri for krasj.
        per_id = {r["id"]: r for r in res["oppgaver"]}
        forventet = ["krit", "folg", "rute"]
        for opg, vent in zip(oppgaver, forventet, strict=False):
            r = per_id.get(opg.id)
            if r:
                self.assertEqual(
                    r["tid_status"],
                    vent,
                    "«{}» fikk status «{}», forventet «{}»".format(
                        opg.name, r["tid_status"], vent
                    ),
                )
                # Frist skal være en ren datostreng, ikke et tidsstempel.
                self.assertRegex(
                    str(r["frist"]),
                    r"^\d{4}-\d{2}-\d{2}$",
                    "Frist skal være dato uten klokkeslett, fikk {!r}".format(
                        r["frist"]
                    ),
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
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        # Siste dag i et 7-ukers vindu som starter denne uka
        start = i_dag - timedelta(days=i_dag.weekday())
        siste_dag = start + timedelta(weeks=7) - timedelta(days=1)

        sen = self.env["project.task"].create(
            {
                "name": "TEST frist kl 15 siste dag",
                "project_id": prosjekt.id,
                # 15:00 samme dag — ville falt utenfor med midnatt-grense
                "date_deadline": fields.Datetime.to_datetime(
                    f"{fields.Date.to_string(siste_dag)} 15:00:00"
                ),
            }
        )

        res = self.Data.get_oppgaver_over_tid(antall=7)
        ider = {r["id"] for r in res["oppgaver"]}
        self.assertIn(
            sen.id,
            ider,
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
            "{} av {} oppgaver mangler BÅDE start og frist og kan ikke tegnes. "
            "Første: «{}». Udaterte oppgaver hører hjemme i Liste/Kanban, ikke i Gantt.".format(
                len(udaterte),
                len(res["oppgaver"]),
                udaterte[0]["navn"] if udaterte else "",
            ),
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
        t = self.env["project.task"].create(
            {
                "name": "TEST uten sjekkliste",
                "project_id": prosjekt.id,
            }
        )
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
        t = self.env["project.task"].create(
            {
                "name": "TEST med sjekkliste",
                "project_id": prosjekt.id,
            }
        )
        self.env["fiq.sjekkliste"].create(
            {
                "name": "Testliste",
                "task_id": t.id,
                "punkt_ids": [(0, 0, {"name": "Krever dok", "krav_dok": True})],
            }
        )

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
        self.assertTrue(
            p["mangler"],
            "Brukeren må få vite HVA som mangler, ikke bare at det er sperret",
        )

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

    # ---------- RISIKO-DOMMEN (krav 7) — flatens side ----------
    #
    # 📌 FLYTTET til tests/test_prj_data_lag.py (23.07, datalags-delingen):
    #    de ni rene beregningstestene på `_risiko_dom` og `_risiko_hvorfor`
    #    (i_balanse · tett_budsjett · avgjores ×2 · over_budsjett · ferdig ·
    #     penger uten fremdrift · hvorfor-i-klartekst · hvorfor-aldri-tom).
    #    De regner på oppdiktede tall og rører aldri flaten.
    #
    # 🔑 DE TO UNDER BLIR HER. De påstår ikke noe om regnestykket — de påstår
    #    at dommen FAKTISK NÅR RADENE flaten tegner. Det er flatens kontrakt,
    #    og det var nettopp den påstanden som sviktet 23.07: dommen var bygget
    #    i 1.26.0 og vist i null versjoner.

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
                "Begrunnelsen var tom for {}".format(p["navn"]),
            )

    # 📌 FLYTTET til tests/test_prj_data_lag.py:
    #    test_risiko_penger_brukt_uten_fremdrift_er_ikke_i_balanse

    # ---------- KR-BOKSEN — mine fire tall til forsiden ----------

    def test_kr_boks_har_teller_og_nevner(self):
        """Fasiten viser «18 / 23» — aldri et nakent tall.

        🔑 «18 i rute» uten «av 23» er ikke en status, det er et tall uten
        målestokk. Forsiden må kunne skrive brøken uten å regne selv.
        """
        b = self.Data.get_kr_boks()
        self.assertIn("prosjekter_i_rute", b)
        self.assertIn("prosjekter_totalt", b)
        self.assertLessEqual(
            b["prosjekter_i_rute"],
            b["prosjekter_totalt"],
            "Teller kan aldri være større enn nevner",
        )

    def test_kr_boks_avvik_er_false_ikke_null(self):
        """🛑 0 ville sagt «ingen avvik». Det kan jeg ikke belegge.

        Det finnes ingen avviksmodell i fiq_gui_prj ennå. `False` sier «vet
        ikke», og forsiden kan skjule feltet i stedet for å vise en påstand
        som ser ut som en måling. Samme disiplin som ellers denne uka:
        fravær av data er ikke det samme som fravær av avvik.
        """
        b = self.Data.get_kr_boks()
        self.assertIs(
            b["avvik_apne"],
            False,
            "Ubygget tall skal være False (vet ikke), aldri 0 (ingen)",
        )

    def test_kr_boks_peker_paa_slot_ikke_xmlid(self):
        """🔴 REGRESJON: xmlid ville tatt brukeren UT av Kontrollrommet.

        Klikk på et tall skal bytte INNMAT så rammen står. Nøkkelen må være
        slot-navnet i `fiq_gui_flates`. Med en xmlid ville `doAction` forlatt
        skallet — nøyaktig feilen som gjorde at hovedmenyen forsvant for
        Gjermund 23.07.
        """
        b = self.Data.get_kr_boks()
        self.assertEqual(b["slot"], "gui_prj")
        self.assertNotIn(
            ".", b["slot"], "En xmlid har punktum; en slot-nøkkel har ikke"
        )

    def test_kortslutninger_returnerer_SAMME_form(self):
        """🔴 REGRESJON funnet 23.07 på et FERSKT bygg.

        `get_ai_arbeid()` returnerte `{spor, tilgjengelig}` når AI KR manglet,
        men `{spor, tilgjengelig, valgt_firma, antall_koblet}` ellers. TO ULIKE
        FORMER fra samme metode — klienten kan ikke lese `res.valgt_firma` uten
        å vite hvilken gren den havnet i.

        🔑 Hvorfor den overlevde: på det gamle bygget var AI KR installert, så
        kortslutningen ble ALDRI kjørt. Testen var grønn i ukevis fordi
        kodeveien aldri ble besøkt. Et tomt bygg avslørte den på første forsøk.

        Samme klasse som `fremdrift = 0`: koden fantes, ingen test hadde vært
        i den. Et ferskt bygg er ikke en ulempe — det er den eneste måten å
        oppdage hva som bare virker ved flaks.
        """
        ai = self.Data.get_ai_arbeid(firma_id=999999)
        for n in ("spor", "tilgjengelig", "valgt_firma", "antall_koblet"):
            self.assertIn(n, ai, f"get_ai_arbeid mangler «{n}» i en av utgangene")

        sj = self.Data.get_sjekklister(oppgave_id=999999999)
        for n in ("tilgjengelig", "lister", "oppgave"):
            self.assertIn(n, sj, f"get_sjekklister mangler «{n}» i en av utgangene")

    def test_risiko_dommen_er_KOBLET_til_flaten(self):
        """🔴 REGRESJON: jeg bygde dommen i 1.26.0 og VISTE DEN ALDRI.

        Null treff på «risiko» i prj.xml, prj.js og prj.scss i fem versjoner.
        Nøyaktig feilen AI KR tok meg i 22.07 med sjekklistene: datalaget
        ferdig, flaten urørt. Jeg kritiserte det hos andre og gjentok det
        fjorten dager senere.

        🔑 Denne testen kan ikke lese JS-filene, men den kan låse kontrakten
        flaten bygger på: feltene MÅ finnes på hver rad, ellers har flaten
        ingenting å vise. Den fanger at noen fjerner feltene fra serveren —
        ikke at noen fjerner dem fra malen. Halv dekning er ærligere enn
        ingen, men jeg noterer grensen.
        """
        res = self.Data.get_prosjektoversikt(grense=10)
        if not res["prosjekter"]:
            self.skipTest("Ingen prosjekter å teste mot")
        lovlige = {
            "i_balanse",
            "tett_budsjett",
            "over_budsjett",
            "tett_tid",
            "avgjores",
            "ferdig",
        }
        for p in res["prosjekter"]:
            self.assertIn(
                p["risiko"],
                lovlige,
                "«{}» har ukjent dom «{}» — flaten kan ikke farge den".format(
                    p["navn"], p["risiko"]
                ),
            )
            self.assertIn("nummer", p, "Risikoraden viser prosjektnummer")
            self.assertIn("forbruk_prosent", p, "Risikoraden viser en stolpe")

    def test_kpi_kortene_fylles_naar_oppgaver_finnes(self):
        """🔴 Gjermund så flaten 23.07: ALLE fem KPI-kort viste 0, Gantt tom.

        To forklaringer var mulige — (A) basen er tom og flaten viser sannheten,
        eller (B) datakoblingen svikter og flaten tegner nuller. Ingen test kunne
        skille dem: den eneste KPI-sjekken var `assertIn("kpi", res)`, som bare
        krever at NØKKELEN finnes. Et tomt oppslagsverk består den.

        🔑 Denne testen OPPRETTER tre oppgaver med kjente frister og krever at
        tallene faktisk stiger. Er den grønn mens flaten viser 0, er basen tom
        (A). Er den rød, svikter koblingen (B). Da er nullene et svar, ikke bare
        et symptom.

        📌 Samme lærdom som resten av uka: «nøkkelen finnes» og «tallet stemmer»
        er to påstander, og bare den andre er verdt noe for den som ser skjermen.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        egne = self.env["project.task"].create(
            [
                {
                    "name": "KPI passert",
                    "project_id": prosjekt.id,
                    "date_deadline": fields.Datetime.to_datetime(
                        i_dag - timedelta(days=2)
                    ),
                },
                {
                    "name": "KPI naer",
                    "project_id": prosjekt.id,
                    "date_deadline": fields.Datetime.to_datetime(
                        i_dag + timedelta(days=2)
                    ),
                },
            ]
        )

        res = self.Data.get_oppgaver_over_tid(antall=7)
        kpi = res.get("kpi") or {}

        self.assertTrue(
            res["oppgaver"],
            "To oppgaver med frister i vinduet ble opprettet, men datasettet er "
            "tomt — koblingen mellom domenet og flaten svikter",
        )

        # 🔴 SKJERPET 24.07 etter at tre spor falt på samme feilklasse i natt:
        # testen målte hva som tilfeldigvis lå i basen, ikke koden.
        #
        # Her sto bare «kritisk + følg opp > 0». I en base med mange oppgaver
        # ville ANDRES oppgaver gitt grønt selv om MINE to falt utenfor
        # grensen — `get_oppgaver_over_tid` henter 400 rader sortert på
        # `project_id, fiq_wbs_number, sequence, id`, så nye oppgaver havner
        # bakerst. Testen ville bestått av feil grunn.
        #
        # 🔑 KRs mønster: avgrens til DINE egne rader framfor å heve grensen.
        # «Et høyere tall ville bare flyttet den samme antakelsen lenger ut.»
        mine = [r for r in res["oppgaver"] if r["id"] in egne.ids]
        self.assertEqual(
            len(mine),
            2,
            "De to opprettede oppgavene kom ikke med i datasettet — de har "
            f"frister i vinduet og skal alltid være der. Fant {len(mine)} av 2.",
        )
        self.assertGreater(
            (kpi.get("kritisk") or 0) + (kpi.get("folg_opp") or 0),
            0,
            "Oppgaver med passert frist og frist om to dager finnes, men både "
            "«kritisk» og «følg opp» står på 0. Kortene fylles ikke.",
        )

    def test_ai_nevneren_er_ikke_null_naar_oppgaver_finnes(self):
        """«GJORT AV AI 0/0» — nevneren var også 0 på Gjermunds skjerm.

        🔑 Det skiller «ingen er gjort av AI» (0/12, et ærlig svar) fra «vi har
        ingen data» (0/0, som ser ut som en feil). Nevneren er antall oppgaver
        totalt — den kan bare være 0 hvis datasettet er tomt.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        self.env["project.task"].create(
            {
                "name": "AI-nevner",
                "project_id": prosjekt.id,
                "date_deadline": fields.Datetime.to_datetime(i_dag + timedelta(days=1)),
            }
        )

        kpi = self.Data.get_oppgaver_over_tid(antall=7).get("kpi") or {}
        self.assertGreater(
            kpi.get("ai_totalt") or 0,
            0,
            "En oppgave med frist i morgen finnes, men «gjort av AI»-nevneren er "
            "0. 0/0 ser ut som manglende data, ikke som et svar.",
        )

    def test_oppgave_uten_firma_forsvinner_ikke_stille(self):
        """🔴 MULIG ÅRSAK til at Gjermund så 0 overalt (23.07).

        `_firma_domene` bruker `("company_id", "in", tillatte)`. Et Odoo-domene
        med `in` slipper IKKE gjennom rader der feltet er tomt. Har en oppgave
        eller et prosjekt `company_id = False` — fullt lovlig i Odoo — faller den
        ut av HVER eneste spørring i flaten, uten feilmelding.

        🔑 Det er den farligste formen: ingen krasj, ingen advarsel, bare tall
        som er for lave. Nøyaktig samme klasse som Gantt-domenet 22.07, der 379
        av 400 rader var utegnbare mens alt så grønt ut.

        Denne testen dokumenterer atferden. Er den grønn, håndteres tomt firma
        riktig.

        🔴 RETTET RÅD 24.07 — den forrige setningen her sa: «er den rød, skal
        domenet utvides med `'|', ('company_id', '=', False)`». **Det rådet var
        feil**, og port 6 ble skjerpet samme kveld nettopp på grunn av tre feil
        av denne klassen — én av dem min.

        🔑 Regelen: *en test som oppretter data UTENFOR domenet koden filtrerer
        på, er grønn når koden er tom og rød når den virker.* Å utvide domenet
        for å få grønt ville sluppet gjennom oppgaver uten firma i en flate som
        skal være tenant-isolert. **Domenet er riktig; det er testdataen som
        eventuelt ligger utenfor.**

        Derfor hopper testen over (under) når firma arves fra prosjektet — da
        KAN tilstanden ikke oppstå, og en test av noe umulig beviser ingenting.
        Blir den rød i en base der tomt firma faktisk finnes, er spørsmålet om
        SLIKE oppgaver skal vises i det hele tatt — et tenant-spørsmål for
        Gjermund, ikke en domene-endring jeg tar selv.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        i_dag = fields.Date.context_today(self.Data)
        opg = self.env["project.task"].create(
            {
                "name": "Uten firma",
                "project_id": prosjekt.id,
                "date_deadline": fields.Datetime.to_datetime(i_dag + timedelta(days=1)),
            }
        )
        if opg.company_id:
            self.skipTest(
                "Oppgaven arvet firma fra prosjektet — tomt firma "
                "kan ikke oppstå i denne basen"
            )

        res = self.Data.get_oppgaver_over_tid(antall=7)
        self.assertIn(
            opg.id,
            [r["id"] for r in res["oppgaver"]],
            "En oppgave uten firma forsvant fra flaten uten feilmelding. "
            "Domenet må også slippe gjennom company_id = False.",
        )

    # ---------- SJEKKLISTE SOM VALGFRI NABO ----------

    def test_flaten_taaler_at_sjekkliste_motoren_mangler(self):
        """🔴 Sjekklisten er et TILLEGG, ikke en forutsetning for å se prosjekter.

        `fiq_sjekkliste` ble skilt ut som egen modul 24.07. Feltene
        `fiq_sjekkliste_ids` og `fiq_sjekkliste_fremdrift` bor der nå, og ble
        lest sju steder i datalaget UTEN vakt.

        🔑 Uten vakten ville et AttributeError felt `_node()`,
        `get_oppgaver_over_tid()` OG `get_oppgaver()` — altså Gantt, Liste og
        Kanban samtidig. Ikke en tom kolonne: en flate som ikke laster.

        Testen bruker en attrapp UTEN feltene, fordi modulen er installert i
        denne basen og tilstanden ellers ikke kan oppstå. Det er samme grep som
        `test_prioritet_ukjent_verdi_faller_til_normal`: vi kan ikke avinstallere
        en nabo midt i en test, men vi kan spørre vakten hva den gjør.

        📌 Hvilken feil fanger den om tre måneder? At noen fjerner vakten fordi
        «feltet finnes jo alltid» — som det gjør, helt til motoren avinstalleres.
        """

        class UtenSjekkliste:
            _fields = {}

        self.assertEqual(
            self.Data._sjekkliste_fremdrift(UtenSjekkliste()),
            0.0,
            "Uten motoren skal fremdriften være 0.0 — ikke felle flaten",
        )

    def test_sjekkliste_fremdrift_avrundes_til_en_desimal(self):
        """Flaten viser «12,3 %» — ikke «12,333333333».

        🔑 Avrundingen skjedde tidligere på syv ulike steder. Nå gjør vakten
        det ett sted. Testen låser at den fortsatt gjør det: fjerner noen
        `round()` i vakten, får flaten et tall den ikke kan tegne pent.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        oppgave = self.env["project.task"].create(
            {"name": "TEST avrunding", "project_id": prosjekt.id}
        )
        verdi = self.Data._sjekkliste_fremdrift(oppgave)
        self.assertEqual(
            verdi,
            round(verdi, 1),
            "Fremdriften er ikke avrundet til én desimal",
        )

    def test_sjekklister_gir_alltid_noe_som_kan_telles_og_itereres(self):
        """Kontrakten mellom datalaget og flaten: `len()` og `for` må virke.

        🔑 Vakten returnerer `task.browse()` — en TOM MENGDE av samme modell,
        ikke `[]` og ikke `None`. Forskjellen betyr noe: `len(None)` kaster,
        og en liste tåler ikke `.sorted()` eller `.mapped()` som koden bruker
        lenger nede.

        📌 Hvilken feil fanger den? At noen «forenkler» vakten til `return []`
        fordi det ser renere ut — og at `get_sjekklister()` da kaster på første
        oppgave uten sjekklister.
        """
        prosjekt = self.Project.search(self._prosjekt_domene_for_test(), limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å teste mot")

        oppgave = self.env["project.task"].create(
            {"name": "TEST tom mengde", "project_id": prosjekt.id}
        )
        lister = self.Data._sjekklister(oppgave)
        self.assertEqual(len(lister), 0, "Ny oppgave skal ikke ha sjekklister")
        self.assertEqual(
            list(lister), [], "Mengden skal kunne itereres, ikke bare telles"
        )
        # `.mapped()` finnes bare på en recordset — beviser at det ikke er en liste.
        self.assertEqual(lister.mapped("id"), [])
