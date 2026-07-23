# -*- coding: utf-8 -*-
"""Tester for stadiene — oppgaver flytter seg, de forsvinner ikke.

Gjermund 22.07.2026: «må flyttes fra et stadie til neste eller blir jo listen
helt statisk». Fasit: artifact 72aae7c9.

🔑 VIKTIGSTE TEST: `test_svar_flytter_oppgaven`.
Et svar som ikke flytter noe er et svar som forsvinner — spørsmålet blir stående
i køen, og han svarer på det samme igjen i morgen.
"""

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestStadie(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.S = cls.env["fiq.ai.stadie"]
        cls.G = cls.env["fiq.ai.godkjenning"]
        cls.Type = cls.env["project.task.type"]
        cls.S.sikre_stadier()
        cls.prosjekt = cls.env["project.project"].create({"name": "Stadie-test"})
        cls.oppgave = cls.env["project.task"].create({
            "name": "Testoppgave", "project_id": cls.prosjekt.id})

    # ── SEEDING ─────────────────────────────────────────────────────────────
    def test_alle_fem_stadier_finnes(self):
        koder = [s["kode"] for s in self.S.stadie_liste()]
        self.assertEqual(koder, ["ko", "venter", "arbeid", "ks", "ferdig"])

    def test_navnene_er_gjermunds_med_stor_forbokstav(self):
        navn = {s["kode"]: s["navn"] for s in self.S.stadie_liste()}
        self.assertEqual(navn["ko"], "I Kø")
        self.assertEqual(navn["venter"], "Venter Avklaring")
        self.assertEqual(navn["arbeid"], "I Arbeid")
        self.assertEqual(navn["ks"], "Kvalitetssikring")
        self.assertEqual(navn["ferdig"], "Ferdig")

    def test_gjermunds_farger(self):
        """Rød på «Venter Avklaring» og grønn på «Ferdig» er hans egne valg."""
        farge = {s["kode"]: s["farge"] for s in self.S.stadie_liste()}
        self.assertEqual(farge["venter"], "#c81414")
        self.assertEqual(farge["ferdig"], "#00a844")

    def test_seeding_lager_ikke_duplikater(self):
        """Idempotent. Kjøres ved hver flate-åpning — må tåle det."""
        for _ in range(3):
            self.S.sikre_stadier()
        self.assertEqual(self.Type.search_count([("fiq_ai_kode", "=", "ko")]), 1)

    def test_eksisterende_stadium_med_samme_navn_merkes_ikke_dupliseres(self):
        """Finnes stadiet fra før uten kode, skal det MERKES — ikke få en tvilling.

        🔴 TESTEN VAR FEIL SKREVET (rettet 23.07, fanget på DEV 35275074):
        Første utgave opprettet et NYTT «Kvalitetssikring» ved siden av det
        `setUpClass` allerede hadde seedet, avmerket begge, og forventet så ÉN
        post. Da var det to før koden i det hele tatt kjørte — testen målte sin
        egen oppsett-feil, ikke `sikre_stadier()`.

        Riktig oppsett: ta stadiet som ALT finnes, fjern kodemerket, og se at
        seedingen finner det igjen på navn framfor å lage et nytt.
        Samme feilklasse som huset har brukt uka på: målt noe annet enn det som
        skulle måles.
        """
        fantes = self.Type.search([("fiq_ai_kode", "=", "ks")], limit=1)
        self.assertTrue(fantes, "setUpClass seedet ikke «Kvalitetssikring».")
        antall_for = self.Type.search_count([("name", "=ilike", "Kvalitetssikring")])

        fantes.write({"fiq_ai_kode": False})     # nå ser det ut som et vanlig Odoo-stadium
        self.S.sikre_stadier()

        self.assertEqual(
            self.Type.search_count([("name", "=ilike", "Kvalitetssikring")]), antall_for,
            "Det ble laget et duplikat av et stadium som allerede fantes.")
        self.assertEqual(
            fantes.fiq_ai_kode, "ks",
            "Det eksisterende stadiet ble ikke merket — da er gjenbruken bare tilsynelatende.")

    # ── FLYTTING ────────────────────────────────────────────────────────────
    def test_flytt_setter_native_stage_id(self):
        """Vi bruker Odoos EGET felt — ikke en parallell tabell.

        Kanon: «Odoo uten KR skal virke.» Setter vi ikke stage_id, slutter
        Odoos egen Kanban å vise hvor oppgaven står.
        """
        r = self.S.flytt_til(self.oppgave.id, "arbeid")
        self.assertTrue(r["ok"])
        self.assertEqual(self.oppgave.stage_id.fiq_ai_kode, "arbeid")

    def test_flytt_til_ukjent_stadium_avvises(self):
        r = self.S.flytt_til(self.oppgave.id, "finnes_ikke")
        self.assertFalse(r["ok"])

    def test_flytt_paa_slettet_oppgave_gir_feil_ikke_krasj(self):
        r = self.S.flytt_til(999999999, "arbeid")
        self.assertFalse(r["ok"])

    # ── SVAR → FLYTTING (kjernen) ───────────────────────────────────────────
    def test_svar_flytter_oppgaven(self):
        """🔑 «Svarer han → oppgaven flyttes til I Arbeid.»"""
        g = self.G.browse(self.G.spor(
            "Skal vi kjøre?", task_id=self.oppgave.id)["id"])
        g.svar_paa("godkjent")
        self.assertEqual(self.oppgave.stage_id.fiq_ai_kode, "arbeid")

    def test_senere_legger_tilbake_i_ko(self):
        """«Senere» er ikke «nei» — den skal tilbake i køen, ikke forsvinne."""
        self.S.flytt_til(self.oppgave.id, "arbeid")
        g = self.G.browse(self.G.spor(
            "Skaff nøkkel?", art="oppgave", task_id=self.oppgave.id)["id"])
        g.svar_paa("senere")
        self.assertEqual(self.oppgave.stage_id.fiq_ai_kode, "ko")

    def test_svar_uten_oppgave_krasjer_ikke(self):
        g = self.G.browse(self.G.spor("Uten oppgave?")["id"])
        g.svar_paa("godkjent")
        self.assertEqual(g.svar, "godkjent")

    def test_svaret_staar_selv_om_flyttingen_feiler(self):
        """Svaret er det viktigste — flyttingen er en bekvemmelighet.

        Feiler stadiebyttet, skal ikke Gjermunds svar rulles tilbake med det.
        """
        g = self.G.browse(self.G.spor("Test?", task_id=self.oppgave.id)["id"])
        self.oppgave.unlink()
        g.svar_paa("godkjent")
        self.assertEqual(g.svar, "godkjent")

    # ── FLATEN ──────────────────────────────────────────────────────────────
    def test_get_styring_gir_alt_i_ett_kall(self):
        """Ett kall, ikke fire — KR-ytelsesmålingen 19.07 fant sekvensielle kall."""
        d = self.env["fiq.gui.ai.kr.data"].get_styring()
        for n in ("stadier", "spor", "oppgaver", "sporsmaal"):
            self.assertIn(n, d)
        self.assertEqual(len(d["stadier"]), 5)

    def test_kommentar_havner_i_chatteren(self):
        Data = self.env["fiq.gui.ai.kr.data"]
        t = self.env["project.task"].create({"name": "Kommentar-test"})
        self.assertTrue(Data.skriv_kommentar(t.id, "Dette er en test")["ok"])
        logg = Data.get_kommentarlogg(t.id)
        self.assertTrue(logg["finnes"])
        self.assertTrue(any("Dette er en test" in (l["tekst"] or "") for l in logg["logg"]))

    def test_tom_kommentar_avvises(self):
        Data = self.env["fiq.gui.ai.kr.data"]
        t = self.env["project.task"].create({"name": "Tom-test"})
        self.assertFalse(Data.skriv_kommentar(t.id, "   ")["ok"])

    def test_oppgave_uten_eier_merkes_som_ai(self):
        """user_ids tom = AI. Samme konvensjon som Prosjekt (00.03) — avklart 22.07
        så vi ikke viser ulike tall for samme sak."""
        t = self.env["project.task"].create({"name": "AI-oppgave", "user_ids": [(5, 0, 0)]})
        rad = [o for o in self.env["fiq.gui.ai.kr.data"].get_styring_oppgaver()
               if o["id"] == t.id]
        self.assertTrue(rad)
        self.assertTrue(rad[0]["er_ai"])
        self.assertEqual(rad[0]["eier"], "AI")
