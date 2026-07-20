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

    def test_kr_boks_teller_kun_apne(self):
        """Samleboksen teller åpne muligheter — aldri vunne.

        Dette er kontrakten mot Kontrollrommet: `totalt` er «åpen pipeline»,
        ikke «alle salgsmuligheter som finnes».
        """
        boks = self.Data.get_kr_boks()
        if boks is None:
            self.skipTest("Ingen åpne salgsmuligheter i denne basen.")
        apne = self.Lead.search_count([
            ("type", "=", "opportunity"),
            ("stage_id.is_won", "=", False),
        ])
        self.assertEqual(boks["totalt"], apne)

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
