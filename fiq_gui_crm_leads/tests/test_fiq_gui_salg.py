"""Tester for salgsflatens datakilde.

🛑 `post_install` er IKKE valgfritt. Odoos standard (`at_install`) kjører testen
   MIDT i modulens installasjon, da inneholder registryet kun modulens egne
   `depends`. Andre installerte moduler har lagt NOT NULL-kolonner på de samme
   tabellene (f.eks. `billing_type` fra sale_timesheet på project.project,
   `group_rfq` fra purchase_stock på res.partner). Defaulten settes av Odoo i
   Python, skranken ligger i Postgres — under at_install finnes feltet ikke i
   registryet, ingen default anvendes, og INSERT feiler med NotNullViolation.
   Dette holdt tre KR-tester røde uten at noen visste det.
"""

from odoo import fields
from odoo.tests import TransactionCase, tagged


# 🛑 «fiq» er PÅKREVD i tillegg til post_install: CI kjører --test-tags=fiq.
#    Uten den hoppes testene over, resultatet blir «0 of 0 tests», og gaten
#    melder grønt uten at én test har kjørt. Disse åtte testene sto uten
#    taggen fram til 24.07 — de ville aldri kjørt i CI.
@tagged("post_install", "-at_install", "fiq")
class TestFiqGuiSalg(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.salg.data"]
        cls.Lead = cls.env["crm.lead"]

        # Testene OPPRETTER sin egen tilstand — de leser ikke basens.
        #
        # Development bygger TOM base med Odoos demodata; Staging har ekte
        # FIQ-data. Uten egen tilstand oppfører testene seg ulikt de to
        # stedene, og en test som «hopper over» ser ut som en test som
        # passerte. Her lages et minimalt, komplett pipeline-bilde: ett
        # aktivt stadium, ett vunnet, ett tapt — det er alt koden skiller på.
        Stadium = cls.env["crm.stage"]
        cls.aktivt_stadium = Stadium.create(
            {
                "name": "02.01 Testaktiv",
                "sequence": 900,
            }
        )
        cls.vunnet_stadium = Stadium.create(
            {
                "name": "4.00 Testvunnet",
                "sequence": 901,
                "is_won": True,
            }
        )

        # 🛑 SALGSMULIGHETER MÅ HA KUNDE — `name` er BEREGNET, ikke fritekst.
        #
        # FIQ-modulen `crm_name` overstyrer `crm.lead.name` med et uttrykk fra
        # `ir.config_parameter` (`crm_name.crm_lead_name_expression`), som
        # normalt gir kundens kortnavn. Setter man `name` direkte, blir det
        # overskrevet — og finnes ingen kunde, returnerer uttrykket `False`.
        # Da feiler `crm_name`s egen linje `lead.name.startswith("NewId")`
        # med «'bool' object has no attribute 'startswith'», og HELE testklassen
        # ryker i setUpClass før en eneste test kjører.
        #
        # Funnet 22.07.2026 med `-u --test-tags`. Ren installasjon (`-i`) traff
        # det ALDRI, fordi `crm_name` ikke var lastet da. Gjermund forutså det:
        # «-u test vil avsløre noen av disse». Derfor: gi hver sak en kunde, og
        # la Odoo eie navnet.
        # Uttrykket crm_name bygger navnet fra er IKKE satt på en tom
        # Dev-base (målt: ir_config_parameter «crm_name%» ga 0 rader). Da
        # returnerer uttrykket ingenting, navnet blir tomt, og INSERT feiler
        # på NOT NULL. På fiqas ER parameteren satt, så feilen finnes ikke
        # der — samme kode, ulik konfigurasjon. Testen setter den selv i
        # stedet for å anta at basen har den.
        #
        # Syntaksen er en F-STRENG med variabelen `r` (verifisert i kilden:
        # base_mixin_expression_value/models/expression_value_mixin.py:39
        # → safe_eval(f"f{repr(expression)}", {"r": record})). Altså
        # «{r.felt}», ikke «object.felt» — sistnevnte ville gitt tom streng.
        #
        # 🛑 MÅ settes FØR leadene opprettes: crm_name.create() beregner
        # navnet umiddelbart etter super().create().
        cls.env["ir.config_parameter"].sudo().set_param(
            "crm_name.crm_lead_name_expression",
            "{r.partner_id.short_name}",
        )

        # Kunden må ha `short_name`: crm_name leser nettopp det feltet
        # (partner_short_name = related partner_id.short_name).
        cls.testkunde = cls.env["res.partner"].create(
            {
                "name": "Testkunde Salgsflate",
                "short_name": "TESTSALG",
                "is_company": True,
            }
        )

        i_dag = fields.Date.context_today(cls.Data)
        # Én sak over frist i et aktivt stadium = én sak som skal HASTE.
        cls.forfalt_sak = cls.Lead.create(
            {
                # `name` MÅ med i create-kallet: crm_lead.name er NOT NULL i
                # basen, og crm_name beregner navnet FØRST ETTER super().create()
                # (crm_name/models/crm_lead.py:18-20) — altså etter at INSERT
                # allerede har kjørt. Uten `name` her feiler INSERT før crm_name
                # får sjansen. Verdien blir uansett overskrevet av det beregnede
                # navnet rett etterpå; den er kun en gyldig plassholder for INSERT.
                "name": "Testsak",
                "partner_id": cls.testkunde.id,
                "type": "opportunity",
                "stage_id": cls.aktivt_stadium.id,
                "date_deadline": fields.Date.subtract(i_dag, days=10),
                "expected_revenue": 50000.0,
            }
        )
        # Én vunnet sak: skal ALDRI telle som åpen pipeline.
        cls.vunnet_sak = cls.Lead.create(
            {
                # `name` MÅ med i create-kallet: crm_lead.name er NOT NULL i
                # basen, og crm_name beregner navnet FØRST ETTER super().create()
                # (crm_name/models/crm_lead.py:18-20) — altså etter at INSERT
                # allerede har kjørt. Uten `name` her feiler INSERT før crm_name
                # får sjansen. Verdien blir uansett overskrevet av det beregnede
                # navnet rett etterpå; den er kun en gyldig plassholder for INSERT.
                "name": "Testsak",
                "partner_id": cls.testkunde.id,
                "type": "opportunity",
                "stage_id": cls.vunnet_stadium.id,
                "expected_revenue": 80000.0,
            }
        )

    def test_pipeline_har_alle_stadier(self):
        """Pipelinen viser hvert stadium i basen — også de tomme.

        Et hull i pipelinen er informasjon: ser man at «Tilbud sendt» er tom,
        vet man hvor det stopper. Skjuler man tomme stadier, ser flaten
        friskere ut enn virkeligheten.
        """
        stadier = self.Data.get_pipeline()
        self.assertEqual(
            len(stadier),
            self.env["crm.stage"].search_count([]),
            "Alle stadier skal med, også de uten salgsmuligheter.",
        )

    def test_pipeline_folger_stadienes_rekkefolge(self):
        """Rekkefølgen er stadienes egen (`sequence`), ikke alfabetisk.

        En pipeline leses fra venstre mot høyre som en reise. Sorterer man på
        navn, havner «9.99 Lost» midt inne i løpet.
        """
        stadier = self.Data.get_pipeline()
        rekkefolge = [s["id"] for s in stadier]
        forventet = self.env["crm.stage"].search([], order="sequence, id").ids
        self.assertEqual(rekkefolge, forventet)

    def test_vunnet_er_merket(self):
        """Vunne stadier merkes, så flaten kan dempe dem.

        Uten merket ville en vunnet handel telt som åpen pipeline — det ville
        blåst opp tallet med alt firmaet noen gang har vunnet.
        """
        stadier = self.Data.get_pipeline()
        vunne_i_basen = self.env["crm.stage"].search([("is_won", "=", True)]).ids
        merket = [s["id"] for s in stadier if s["vunnet"]]
        self.assertEqual(sorted(merket), sorted(vunne_i_basen))

    def test_kr_boks_teller_kun_aktive_stadier(self):
        """Samleboksen teller KUN aktive stadier — verken vunnet eller tapt.

        Dette er kontrakten mot Kontrollrommet: `totalt` er «åpen pipeline»,
        ikke «alle salgsmuligheter som finnes».
        """
        # setUpClass har opprettet minst én aktiv sak, så boksen SKAL finnes.
        # Ingen skipTest her: en test som hopper over seg selv ser ut som en
        # test som passerte.
        boks = self.Data.get_kr_boks()
        self.assertIsNotNone(boks, "Med en aktiv sak skal boksen finnes.")
        avsluttede = self.Data._avsluttede_stadier(self.Data).ids
        aktive = self.Lead.search_count(
            [
                ("type", "=", "opportunity"),
                ("stage_id.is_won", "=", False),
                ("stage_id", "not in", avsluttede),
            ]
        )
        self.assertEqual(boks["totalt"], aktive)

    def test_tapte_teller_ikke_som_apen_pipeline(self):
        """En TAPT sak skal aldri telle som åpen pipeline.

        REGRESJONSTEST — dette var en ekte feil i første utgave (20.07.2026).
        Odoo har `is_won` på stadiet, men INGEN `is_lost`: et tapt salg
        forventes arkivert. På fiqas er det ikke gjort — stadiet «9.99 Tapt»
        hadde 25 AKTIVE saker. Boksen meldte derfor «26 av 28 haster», med én
        sak 925 dager over frist. Teknisk riktig, praktisk verdiløst.

        Testen lager en fersk tapt sak som IKKE er arkivert — nøyaktig
        tilstanden som lurte oss — og krever at den holdes utenfor.

        🛑 TESTEN OPPRETTER STADIET SELV — den leter det ikke opp.
        Første utgave søkte etter et eksisterende «9.99»-stadium og kalte
        `skipTest` om det manglet. Det ville gjort testen VERDILØS på
        Development, som bygger tom base med Odoos demodata (stadiene heter
        New/Qualified/Proposition/Won — ingen 9.99). Testen ville hoppet over
        seg selv, og et grønt bygg ville sett ut som bevis for at tapt-filteret
        virker uten å ha prøvd det. Nøyaktig familien «det som ble målt, var
        ikke det som kjørte» ([[00_FERDIG]] port 6: testen må OPPRETTE
        tilstanden den verner mot, ikke bare lese den).
        """
        tapt_stadium = self.env["crm.stage"].create(
            {
                "name": "9.99 Testtapt",
                "sequence": 999,
                # is_won bevisst usatt: det er nettopp poenget. Odoo har ingen
                # `is_lost`, så koden må kjenne igjen tapt på nummerprefikset.
            }
        )

        for_boks = self.Data.get_kr_boks()
        for_antall = for_boks["totalt"] if for_boks else 0

        self.Lead.create(
            {
                # `name` som plassholder for INSERT, kunde for det beregnede
                # navnet. Se setUpClass for hvorfor begge trengs.
                "name": "Regresjonstest tapt sak",
                "partner_id": self.testkunde.id,
                "type": "opportunity",
                "stage_id": tapt_stadium.id,
                "active": True,  # ikke arkivert — det er hele poenget
                "expected_revenue": 999999.0,
            }
        )

        etter_boks = self.Data.get_kr_boks()
        etter_antall = etter_boks["totalt"] if etter_boks else 0
        self.assertEqual(
            etter_antall,
            for_antall,
            "En tapt sak som ikke er arkivert skal ikke øke åpen pipeline.",
        )

    def test_avsluttede_stadier_er_merket_i_pipelinen(self):
        """Både vunnet og tapt merkes `avsluttet`, så flaten kan dempe dem.

        Pipelinen SKJULER dem ikke — man skal se at 25 saker er tapt. Men de
        skal ikke konkurrere visuelt med arbeid som venter.
        """
        stadier = self.Data.get_pipeline()
        avsluttede = self.Data._avsluttede_stadier(self.Data).ids
        for stadium in stadier:
            self.assertEqual(
                stadium["avsluttet"],
                stadium["id"] in avsluttede,
                f"Stadiet «{stadium['navn']}» er feilmerket.",
            )

    def test_kr_boks_har_kontraktens_form(self):
        """Boksen må ha nøyaktig de nøklene Kontrollrommet leser.

        Mangler en nøkkel, faller boksen ut på forsiden — og fordi KR fanger
        feilen per flate (savepoint), skjer det STILLE. Ingen feilmelding,
        bare en boks som aldri vises.
        """
        boks = self.Data.get_kr_boks()
        self.assertIsNotNone(boks, "Med en aktiv sak skal boksen finnes.")
        for noekkel in ("haster", "i_dag", "totalt", "linjer"):
            self.assertIn(noekkel, boks)
        for linje in boks["linjer"]:
            self.assertIn("tekst", linje)
            self.assertIn("res_id", linje)

        # Den forfalte testsaken fra setUpClass SKAL være med i haster-tallet.
        # Uten denne sjekken kunne boksen returnert riktig FORM med gale TALL.
        self.assertGreaterEqual(
            boks["haster"],
            1,
            "En sak 10 dager over frist i et aktivt stadium skal haste.",
        )

    def test_kr_boks_gir_ingenting_naar_pipelinen_er_tom(self):
        """Tom pipeline gir INGEN boks — ikke en boks med 0.

        «Ingenting haster» og «vi har ingen data» er to ulike påstander.
        En nullboks sier det første når det andre er sant.
        """
        tomt = self.Data.with_context(active_test=True)
        alle = self.Lead.search([("type", "=", "opportunity")])
        alle.write({"active": False})
        self.assertIsNone(tomt.get_kr_boks())
