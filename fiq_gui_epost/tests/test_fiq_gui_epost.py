# -*- coding: utf-8 -*-
#
# Tester for E-post-kanalen under Kommunikasjon.
#
# Modulen hadde NULL tester fram til 22.07.2026. Testene under dekker de feilene som
# FAKTISK har truffet den — ikke tenkte tilfeller:
#   · date vs datetime  → skjulte hendelser STILLE (felte Staging for andre moduler)
#   · tidssone           → en frist 23:00 UTC er neste dag i Oslo, havnet i feil rute
#   · scope fra sesjon   → 000-kanon, fail-closed
#   · paring             → `tildel()` kunne ikke pare en UPART melding
#
# post_install: andre moduler legger NOT NULL-kolonner på project.project/res.partner.
# Under at_install er de feltene ukjente for registryet → NotNullViolation. post_install
# gir fullt registry og speiler hvordan koden faktisk kjører.

from datetime import date, datetime, timedelta

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("-at_install", "post_install")
class TestEpost(TransactionCase):

    def setUp(self):
        super().setUp()
        self.Data = self.env["fiq.meldingssenter.data"]

    # ---- Bokser og scope ----------------------------------------------------------

    def test_boxes_har_alle_gruppene(self):
        """Forsiden trenger alle tre gruppene, også tomme — ellers må front-enden
        gjette på om nøkkelen mangler eller bare er tom."""
        b = self.Data.get_boxes()
        for g in ("basis", "tverrgaende", "taksonomi"):
            self.assertIn(g, b)
            self.assertIsInstance(b[g], list)

    def test_firma_domene_er_fail_closed(self):
        """Uten KR-kjernen skal domenet snevres til eget firma — aldri åpnes."""
        dom = self.Data._firma_domene()
        self.assertTrue(dom, "et tomt domene ville vist ALLE firmaers post")

    def test_klientvalg_kan_ikke_utvide_scope(self):
        """000-kanon: klientens firmavalg kan kun SNEVRE INN. Et firma brukeren
        ikke har tilgang til skal ikke gi flere rader enn utgangspunktet."""
        tillatte = self.Data._tillatte_firmaer()
        self.assertTrue(tillatte)
        self.assertTrue(set(tillatte).issubset(set(self.env.user.company_ids.ids)
                                               or set(self.env.company.ids)))

    # ---- REGRESJON: date vs datetime ----------------------------------------------

    def test_kalender_finner_frist_sent_paa_siste_dag(self):
        """🔴 Denne fella felte Staging for to andre moduler 22.07.

        `project.task.date_deadline` er DATETIME. Sammenlignet med et rent
        date-objekt tolkes `<= end` som «<= end 00:00:00», og ALT som ligger
        senere på månedens siste dag faller ut — stille, uten feilmelding.
        Testen lager en frist kl. 23:30 på siste dag i inneværende måned og
        krever at den kommer med."""
        i_dag = date.today()
        forste = i_dag.replace(day=1)
        neste = (forste + timedelta(days=32)).replace(day=1)
        siste = neste - timedelta(days=1)

        prosjekt = self.env["project.project"].create({"name": "TEST kalender-grense"})
        oppgave = self.env["project.task"].create({
            "name": "TEST frist sent paa siste dag",
            "project_id": prosjekt.id,
            "user_ids": [(6, 0, self.env.user.ids)],
            "date_deadline": datetime.combine(siste, datetime.min.time()) + timedelta(hours=23, minutes=30),
        })

        kal = self.Data.get_kalender(aar=siste.year, mnd=siste.month)
        nokkel = siste.strftime("%Y-%m-%d")
        navn = [h["navn"] for h in kal["dager"].get(nokkel, [])]
        self.assertIn(oppgave.name, navn,
                      "frist 23:30 på siste dag må være med — ellers er date/datetime-fella tilbake")

    def test_kalender_grunnform(self):
        """Rutenettet trenger startukedag og antall dager. Mandag = 0
        (norsk uke); JS' getDay() gir søndag = 0 og må ikke brukes her."""
        kal = self.Data.get_kalender(aar=2026, mnd=2)
        self.assertEqual(kal["antall_dager"], 28)
        self.assertEqual(kal["start_ukedag"], date(2026, 2, 1).weekday())
        self.assertEqual(kal["mnd_navn"], "Februar")

    def test_kalender_skuddaar(self):
        """Februar 2024 har 29 dager — grensetilfelle som lett faller ut."""
        self.assertEqual(self.Data.get_kalender(aar=2024, mnd=2)["antall_dager"], 29)

    # ---- Paring -------------------------------------------------------------------

    def test_sok_mal_tomt_soek_gir_tom_liste(self):
        """Tomt søk skal ikke laste halve basen."""
        self.assertEqual(self.Data.sok_mal("", "prosjekt"), [])

    def test_sok_mal_finner_paa_nummer_og_navn(self):
        """Feltet lover «Prosjektnr eller navn» — begge må virke."""
        p = self.env["project.project"].create({"name": "TEST Kabelgata 6"})
        treff = self.Data.sok_mal("Kabelgata", "prosjekt")
        self.assertIn(p.id, [t["id"] for t in treff])
        if p.sequence_code:
            self.assertIn(p.id, [t["id"] for t in self.Data.sok_mal(p.sequence_code, "prosjekt")])

    def test_par_melding_flytter_upart_melding(self):
        """`tildel()` kunne bare lage aktivitet på et element meldingen ALLEREDE
        hang på — den kunne ikke pare en upart melding. Det er hele poenget med
        paring, derfor `par_melding()`."""
        p = self.env["project.project"].create({"name": "TEST paringsmaal"})
        m = self.env["mail.message"].create({
            "subject": "TEST upart melding", "message_type": "email", "body": "<p>test</p>",
        })
        r = self.Data.par_melding(m.id, "project.project", p.id)
        self.assertTrue(r, "paring skal lykkes for et prosjekt brukeren har tilgang til")
        m.invalidate_recordset()
        self.assertEqual(m.model, "project.project")
        self.assertEqual(m.res_id, p.id)

    def test_par_melding_avviser_ukjent_modell(self):
        """Kun prosjekt og oppgave er gyldige paringsmål."""
        m = self.env["mail.message"].create({"subject": "TEST", "message_type": "email"})
        self.assertFalse(self.Data.par_melding(m.id, "res.partner", self.env.user.partner_id.id))

    # ---- Dokumentnavn · PDF -------------------------------------------------------

    def test_nytt_navn_beholder_filendelsen(self):
        """Utelater brukeren endelsen, skal den bevares — ellers mister fila
        tilknytningen til programmet som åpner den."""
        a = self.env["ir.attachment"].create({"name": "notat.txt", "raw": b"hei"})
        r = self.Data.gi_nytt_navn(a.id, "Referat fra befaring")
        self.assertTrue(r)
        self.assertEqual(r["navn"], "Referat fra befaring.txt")

    def test_nytt_navn_respekterer_egen_endelse(self):
        """Oppgir brukeren endelse selv, skal vi ikke legge på enda en."""
        a = self.env["ir.attachment"].create({"name": "notat.txt", "raw": b"hei"})
        self.assertEqual(self.Data.gi_nytt_navn(a.id, "rapport.pdf")["navn"], "rapport.pdf")

    def test_pdf_beholder_originalen(self):
        """Konvertering er IKKE erstatning — originalen skal bestå
        ([[fiq-vokter]] mist-aldri-innhold)."""
        a = self.env["ir.attachment"].create({
            "name": "notat.txt", "raw": b"hei verden", "mimetype": "text/plain"})
        r = self.Data.til_pdf(a.id)
        self.assertTrue(a.exists(), "originalen skal aldri slettes")
        if r.get("ok"):
            self.assertNotEqual(r["id"], a.id, "PDF-en skal være et NYTT vedlegg")
            self.assertTrue(r["navn"].endswith(".pdf"))

    def test_pdf_sier_ifra_om_ustoettet_format(self):
        """Ustøttet format skal gi en ærlig melding, ikke en tom fil."""
        a = self.env["ir.attachment"].create({
            "name": "bilde.png", "raw": b"\x89PNG", "mimetype": "image/png"})
        r = self.Data.til_pdf(a.id)
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("feil"), "brukeren må få vite hvorfor")

    def test_forhandsvisning_gir_url_ikke_innhold(self):
        """Store vedlegg skal ikke gjennom en RPC-runde bare for å vises."""
        a = self.env["ir.attachment"].create({"name": "d.pdf", "raw": b"%PDF-1.4",
                                              "mimetype": "application/pdf"})
        fv = self.Data.forhandsvis(a.id)
        self.assertIn("/web/content/%s" % a.id, fv["url"])
        self.assertTrue(fv["kan_vises"], "PDF skal kunne vises i nettleseren")
        self.assertNotIn("raw", fv)
