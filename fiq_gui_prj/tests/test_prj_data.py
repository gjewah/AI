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
            if not p["estimerte_timer"]:
                self.assertNotEqual(
                    p["fremdrift_kilde"], "timer",
                    "«%s» har ingen estimerte timer, men oppgir «timer» som "
                    "fremdriftskilde — det er villedende." % p["navn"],
                )

    def test_fremdrift_er_alltid_mellom_0_og_100(self):
        """Overført tid skal aldri gi over 100 % — det bryter fremdriftsstripa."""
        res = self.Data.get_prosjektoversikt(grense=200)
        for p in res["prosjekter"]:
            self.assertGreaterEqual(p["fremdrift"], 0.0, p["navn"])
            self.assertLessEqual(
                p["fremdrift"], 100.0,
                "«%s» viser %s %% — stripa tåler ikke over 100."
                % (p["navn"], p["fremdrift"]),
            )

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
