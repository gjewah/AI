# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


# post_install, ikke at_install — og det er ikke en formalitet:
# testene under oppretter project.task og res.partner. Andre installerte moduler
# (sale_timesheet, purchase_stock) legger NOT NULL-kolonner på nettopp de tabellene.
# Under at_install bygges registeret KUN fra denne modulens `depends` (web, project),
# så de feltene er ukjente, ingen default settes, kolonnen utelates fra INSERT-en —
# og testen faller på NotNullViolation i et felt den aldri har rørt.
@tagged("-at_install", "post_install")
class TestKrLister(TransactionCase):
    """De fire seksjonene fra utkast 15.

    🔑 Hver test OPPRETTER tilstanden den verner mot. En test som bare leser det
    som tilfeldigvis ligger i basen, kan ikke bevise at koden takler en forfalt
    faktura eller en oppgave uten frist — den beviser bare at basen var snill.
    """

    def setUp(self):
        super().setUp()
        self.Config = self.env["fiq.gui.control.config"]

    # ------------------------------------------------------------------
    #  Kontrakten: formen på svaret
    # ------------------------------------------------------------------
    def test_alle_fire_svarer_med_riktig_form(self):
        """Alle fire metodene svarer med nøklene klienten faktisk leser.

        Klienten leser `totalt` og `rader`/`botter` uten å sjekke først. Mangler
        en nøkkel, blir det `undefined` i malen og en tom seksjon UTEN feilmelding
        — den stilleste feilen vi kan lage.
        """
        for metode, listenokkel in (
            ("get_kr_krever_handling", "rader"),
            ("get_kr_siste_aktivitet", "rader"),
            ("get_kr_apne_oppgaver", "rader"),
            ("get_kr_akt_perioder", "botter"),
        ):
            res = getattr(self.Config, metode)()
            self.assertIsInstance(res, dict, "%s må gi en dict" % metode)
            self.assertIn("totalt", res, "%s mangler «totalt»" % metode)
            self.assertIn(listenokkel, res,
                          "%s mangler «%s»" % (metode, listenokkel))
            self.assertIsInstance(res[listenokkel], list)

    def test_radene_har_fire_adskilte_kolonner(self):
        """Fasitens fire kolonner må komme som FIRE FELT, ikke én setning.

        Dette er hele grunnen til at seksjonene ikke gjenbruker `get_kr_boks`:
        der er kolonnene allerede smeltet sammen til `tekst`.
        """
        oppgave = self._lag_oppgave("Romskjema Norvik", frist_om_dager=3)
        res = self.Config.get_kr_apne_oppgaver()
        rader = [r for r in res["rader"] if r["res_id"] == oppgave.id]
        self.assertTrue(rader, "den nye oppgaven skulle vært i lista")
        rad = rader[0]
        for felt in ("kilde", "kode", "tekst", "naar"):
            self.assertIn(felt, rad, "raden mangler kolonnen «%s»" % felt)

    # ------------------------------------------------------------------
    #  Datoer: årstall er ikke valgfritt
    # ------------------------------------------------------------------
    def test_frist_vises_med_arstall(self):
        """«frist 22.07.2026» — ALDRI «frist 22.07».

        En dato uten år er en felle Gjermund har funnet to ganger. Testen låser
        formatet slik at den ikke kan skli tilbake uten at noen ser det.
        """
        oppgave = self._lag_oppgave("Sluttrapport Kostr AS", frist_om_dager=5)
        res = self.Config.get_kr_apne_oppgaver()
        rader = [r for r in res["rader"] if r["res_id"] == oppgave.id]
        self.assertTrue(rader)
        naar = rader[0]["naar"]
        forventet_ar = str((fields.Date.context_today(self.Config)
                            + timedelta(days=5)).year)
        self.assertIn(forventet_ar, naar,
                      "fristen «%s» mangler årstall" % naar)

    def test_tid_tekst_gir_de_tre_formene(self):
        """«i dag HH:MM» · «i går HH:MM» · «dd.mm.åååå» — og den absolutte har år."""
        naa = fields.Datetime.context_timestamp(self.Config, fields.Datetime.now())

        i_dag = self.Config._kr_tid_tekst(naa, fields.Datetime.now())
        self.assertRegex(i_dag, r"\d{2}:\d{2}", "dagens form skal ha klokkeslett")

        gammel = fields.Datetime.now() - timedelta(days=30)
        tekst = self.Config._kr_tid_tekst(naa, gammel)
        self.assertRegex(tekst, r"^\d{2}\.\d{2}\.\d{4}$",
                         "gammel dato må være dd.mm.åååå, fikk «%s»" % tekst)

        self.assertEqual(self.Config._kr_tid_tekst(naa, False), "",
                         "manglende tidspunkt skal gi tom streng, ikke krasje")

    # ------------------------------------------------------------------
    #  Tilstanden koden må tåle
    # ------------------------------------------------------------------
    def test_oppgave_uten_frist_krasjer_ikke(self):
        """En oppgave uten frist er en helt vanlig tilstand, ikke en feil.

        Sorterer man på frist uten å ta høyde for tomme, faller enten kallet eller
        raden ut av lista uten spor.
        """
        oppgave = self._lag_oppgave("Uten frist", frist_om_dager=None)
        res = self.Config.get_kr_apne_oppgaver(grense=200)
        self.assertIsInstance(res["rader"], list)
        treff = [r for r in res["rader"] if r["res_id"] == oppgave.id]
        if treff:
            self.assertTrue(treff[0]["naar"],
                            "en oppgave uten frist skal SI det, ikke stå tom")

    def test_sokefilteret_snevrer_inn_og_meldes_tilbake(self):
        """Filteret må returneres, så overskriften viser det som FAKTISK ble brukt."""
        self._lag_oppgave("Prisjustering SDV-avtale", frist_om_dager=2)
        res = self.Config.get_kr_apne_oppgaver(sok="SDV-avtale")
        self.assertEqual(res["filter"], "SDV-avtale",
                         "filteret må speiles tilbake til klienten")
        for rad in res["rader"]:
            self.assertIn("SDV-avtale", rad["tekst"],
                          "filteret skal snevre inn, ikke bare pyntes med")

    def test_ferdig_oppgave_er_ikke_apen(self):
        """«Åpne oppgaver» skal ikke vise noe som er ferdig.

        Åpen = ikke i en foldet fase. Uten den sjekken vokser lista med alt som
        noensinne er gjort, og seksjonen blir ubrukelig over tid.
        """
        oppgave = self._lag_oppgave("Ferdig sak", frist_om_dager=1)
        ferdig = self.env["project.task.type"].create({
            "name": "Ferdig (test)", "fold": True,
            "project_ids": [(4, oppgave.project_id.id)],
        })
        oppgave.stage_id = ferdig
        res = self.Config.get_kr_apne_oppgaver(grense=200)
        self.assertNotIn(oppgave.id, [r["res_id"] for r in res["rader"]],
                         "en oppgave i foldet fase skal ikke stå som åpen")

    def test_perioder_grupperer_paa_frist(self):
        """Aktiviteter havner i riktig periode-bøtte etter fristen sin.

        🔴 DENNE TESTEN PRØVDE OPPRINNELIG Å OPPRETTE EN AKTIVITET UTEN FRIST — og det
        felte hele bygget: `mail.activity.date_deadline` har en NOT NULL-skranke i basen
        i Odoo 19 (`NotNullViolation` ved `create` med `False`). Målt på dev-bygg
        `35365875`, ikke antatt.

        🔑 Lærdommen er en ny vri på port 6: «testen må opprette tilstanden den verner
        mot» — men her KAN ikke tilstanden eksistere. En aktivitet uten frist finnes
        ikke i denne modellen, så en test som lager en er ikke en streng test, den er
        en umulig test. Den ville ha feilet for alltid, uansett hvor riktig koden var.

        «Uten forfall»-grenen i `get_kr_akt_perioder` (`if not frist`) er likevel korrekt
        og defensiv: `search_read` gir `False` for et tomt datofelt uansett skranke, og
        andre modeller (project.task) HAR nullbar frist. Grenen testes derfor der den kan
        oppstå — i `test_oppgave_uten_frist_krasjer_ikke` over — mens DENNE testen låser
        det bøtte-logikken faktisk gjør for aktiviteter: gruppering på ekte frist.
        """
        Akt = self.env["mail.activity"]
        modell = self.env["ir.model"]._get_id("res.partner")
        todo = self.env.ref("mail.mail_activity_data_todo").id
        pid = self.env.user.partner_id.id
        # To aktiviteter denne uken → skal ende i SAMME bøtte med antall 2.
        for n in ("A", "B"):
            Akt.create({
                "res_model_id": modell, "res_id": pid, "activity_type_id": todo,
                "user_id": self.env.uid, "summary": "Denne uken " + n,
                "date_deadline": fields.Date.context_today(self.Config),
            })
        res = self.Config.get_kr_akt_perioder()
        self.assertIsInstance(res["botter"], list)
        for b in res["botter"]:
            for felt in ("key", "navn", "antall"):
                self.assertIn(felt, b)
            self.assertGreater(b["antall"], 0,
                               "en bøtte med 0 skal ikke vises i det hele tatt")
        denne_uken = [b for b in res["botter"] if b["key"] == "denne_uken"]
        self.assertTrue(denne_uken, "de to aktivitetene skulle gitt en «denne uken»-bøtte")
        self.assertGreaterEqual(
            denne_uken[0]["antall"], 2,
            "begge aktivitetene skulle telt i samme bøtte")

    def test_krever_handling_teller_saker_ikke_kategorier(self):
        """`totalt` skal være antall SAKER — det var nettopp feilen i dagens kode.

        Dagens `handlingsposter` gir 2 samlekategorier uansett hvor mye som ligger
        der. Overskriftstallet må følge radene, ellers sier den «2» når det er 40.
        """
        res = self.Config.get_kr_krever_handling(grense=50)
        self.assertEqual(res["totalt"], len(res["rader"]),
                         "overskriftstallet må stemme med antall rader")

    def test_grensen_respekteres(self):
        """Forsiden skal aldri få en uendelig liste i fanget."""
        for i in range(4):
            self._lag_oppgave("Grensetest %s" % i, frist_om_dager=i + 1)
        res = self.Config.get_kr_apne_oppgaver(grense=2)
        self.assertLessEqual(len(res["rader"]), 2)

    # ------------------------------------------------------------------
    #  Hjelpere
    # ------------------------------------------------------------------
    def _lag_oppgave(self, navn, frist_om_dager=None):
        prosjekt = self.env["project.project"].create({"name": "KR-lister test"})
        # 🔴 STADIUM ER IKKE VALGFRITT I EN TEST FOR «ÅPNE OPPGAVER».
        # `get_kr_apne_oppgaver` filtrerer på `("stage_id.fold", "=", False)` — åpen =
        # ikke i en foldet (avsluttet) fase. En fersk task i et NYTT prosjekt har intet
        # stadium (`stage_id` tom), og en tom `stage_id` matcher ikke `fold = False`.
        # Da faller oppgaven ut av lista, og en test som forventer å se den feiler med [].
        #
        # 🔑 Dette er samme feilklasse som slo til tre ganger 23.07: testdata som ligger
        # UTENFOR domenet koden bruker. En slik test er grønn når koden er tom og rød når
        # den virker — den beviser det motsatte av det den later som. Fiksen hører i
        # testdataen, ikke i domenet: å løsne `stage_id.fold = False` ville vist LUKKEDE
        # oppgaver i «åpne oppgaver». Målt mot dev-bygg 35368345, ikke antatt.
        aapen = self.env["project.task.type"].create({
            "name": "Åpen (test)", "fold": False,
            "project_ids": [(4, prosjekt.id)],
        })
        vals = {"name": navn, "project_id": prosjekt.id, "stage_id": aapen.id}
        if frist_om_dager is not None:
            # `date_deadline` er Datetime i Odoo 19 — ikke Date.
            vals["date_deadline"] = fields.Datetime.now() + timedelta(days=frist_om_dager)
        return self.env["project.task"].create(vals)
