# -*- coding: utf-8 -*-
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

from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestFiqGuiSalg(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.salg.data"]
        cls.Lead = cls.env["crm.lead"]

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
        boks = self.Data.get_kr_boks()
        if boks is None:
            self.skipTest("Ingen åpne salgsmuligheter i denne basen.")
        avsluttede = self.Data._avsluttede_stadier(self.Data).ids
        aktive = self.Lead.search_count([
            ("type", "=", "opportunity"),
            ("stage_id.is_won", "=", False),
            ("stage_id", "not in", avsluttede),
        ])
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
        """
        tapt_stadium = self.env["crm.stage"].search(
            [("name", "=like", "9.99%")], limit=1,
        )
        if not tapt_stadium:
            self.skipTest("Basen har ikke et 9.99-stadium for tapt.")

        for_boks = self.Data.get_kr_boks()
        for_antall = for_boks["totalt"] if for_boks else 0

        self.Lead.create({
            "name": "Regresjonstest tapt sak",
            "type": "opportunity",
            "stage_id": tapt_stadium.id,
            "active": True,          # ikke arkivert — det er hele poenget
            "expected_revenue": 999999.0,
        })

        etter_boks = self.Data.get_kr_boks()
        etter_antall = etter_boks["totalt"] if etter_boks else 0
        self.assertEqual(
            etter_antall, for_antall,
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
                stadium["avsluttet"], stadium["id"] in avsluttede,
                "Stadiet «%s» er feilmerket." % stadium["navn"],
            )

    def test_kr_boks_har_kontraktens_form(self):
        """Boksen må ha nøyaktig de nøklene Kontrollrommet leser.

        Mangler en nøkkel, faller boksen ut på forsiden — og fordi KR fanger
        feilen per flate (savepoint), skjer det STILLE. Ingen feilmelding,
        bare en boks som aldri vises.
        """
        boks = self.Data.get_kr_boks()
        if boks is None:
            self.skipTest("Ingen åpne salgsmuligheter i denne basen.")
        for noekkel in ("haster", "i_dag", "totalt", "linjer"):
            self.assertIn(noekkel, boks)
        for linje in boks["linjer"]:
            self.assertIn("tekst", linje)
            self.assertIn("res_id", linje)

    def test_kr_boks_gir_ingenting_naar_pipelinen_er_tom(self):
        """Tom pipeline gir INGEN boks — ikke en boks med 0.

        «Ingenting haster» og «vi har ingen data» er to ulike påstander.
        En nullboks sier det første når det andre er sant.
        """
        tomt = self.Data.with_context(active_test=True)
        alle = self.Lead.search([("type", "=", "opportunity")])
        alle.write({"active": False})
        self.assertIsNone(tomt.get_kr_boks())
