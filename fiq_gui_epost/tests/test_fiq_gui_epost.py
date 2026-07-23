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

from odoo import fields
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

    def test_kalender_plasserer_frist_i_brukerens_tidssone(self):
        """🔴 To feller i én: date-vs-datetime OG tidssone-grensen.

        `date_deadline` er DATETIME lagret i UTC, men rutenettet viser datoer i
        brukerens tidssone. En frist «siste dag 23:30 UTC» er 01:30 NESTE dag i
        Oslo/Brussel — den skal derfor havne i NESTE måneds rute, ikke i denne.
        Testen krever begge deler: at fristen finnes (hentevinduet må strekke seg
        forbi månedsskiftet), og at den ligger på RIKTIG dato etter konvertering.

        Første kjøring 22.07 avslørte at hentevinduet stoppet ved månedsslutt i
        UTC → fristen ble hentet i én måned og plassert i en annen, og forsvant
        derfor fra begge visningene. Stille, uten feilmelding."""
        i_dag = date.today()
        forste = i_dag.replace(day=1)
        neste_mnd = (forste + timedelta(days=32)).replace(day=1)
        siste = neste_mnd - timedelta(days=1)

        prosjekt = self.env["project.project"].create({"name": "TEST kalender-grense"})
        frist_utc = datetime.combine(siste, datetime.min.time()) + timedelta(hours=23, minutes=30)
        oppgave = self.env["project.task"].create({
            "name": "TEST frist sent paa siste dag",
            "project_id": prosjekt.id,
            "user_ids": [(6, 0, self.env.user.ids)],
            "date_deadline": frist_utc,
        })

        # Hvor HØRER den hjemme etter tidssone-konvertering? Spør Odoo, ikke gjett.
        lokal = fields.Datetime.context_timestamp(self.env["res.users"], frist_utc)
        forventet_dato = lokal.date()

        kal = self.Data.get_kalender(aar=forventet_dato.year, mnd=forventet_dato.month)
        navn = [h["navn"] for h in kal["dager"].get(forventet_dato.strftime("%Y-%m-%d"), [])]
        self.assertIn(oppgave.name, navn,
                      "fristen må ligge på datoen den har i BRUKERENS tidssone — "
                      "faller den ut, er hentevinduet eller konverteringen feil")

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
        # `sequence_code` kommer fra en FIQ/OCA-modul og finnes ikke i alle baser
        # (Dev har den ikke). Sjekk feltet FØR bruk — ellers feiler testen på
        # miljøet, ikke på koden. Samme lærdom som «ID-er overlever ikke oppgradering».
        if "sequence_code" in p._fields and p.sequence_code:
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

    # ---- Overstyring av tverrgående gruppe ----------------------------------------

    def test_tverr_valg_har_automatikk_og_ingen(self):
        """Brukeren må kunne velge BÅDE «la maskinen bestemme» og «ingen gruppe» —
        ellers er overstyringen en enveisdør."""
        koder = [v["kode"] for v in self.Data.get_tverr_valg()]
        self.assertIn("", koder, "må kunne gå tilbake til automatikk")
        self.assertIn("ingen", koder)
        self.assertIn("haster", koder)

    def test_sett_tverr_avviser_ugyldig_kode(self):
        """Vi lagrer aldri noe vi ikke kan vise igjen."""
        m = self.env["mail.message"].create({"subject": "TEST", "message_type": "email"})
        self.assertFalse(self.Data.sett_tverr(m.id, "finnes_ikke"))

    def test_sett_tverr_lagres_og_kan_angres(self):
        """Overstyringen lagres med hvem og når, og tom verdi gir automatikk tilbake."""
        m = self.env["mail.message"].create({"subject": "TEST", "message_type": "email"})
        r = self.Data.sett_tverr(m.id, "haster")
        self.assertEqual(r["kode"], "haster")
        self.assertEqual(self.Data.get_thread(m.id)["tverr_kode"], "haster")
        self.assertTrue(self.Data.get_thread(m.id)["tverr_av"], "hvem som valgte skal vises")
        self.Data.sett_tverr(m.id, "")
        self.assertEqual(self.Data.get_thread(m.id)["tverr_kode"], "",
                         "tom verdi skal gi automatikken tilbake")

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

    def test_brodtekst_gir_HELE_meldingen_ikke_utdrag(self):
        """Gjermund 23.07: «Selve mail teksten kommer dårlig frem. du må vise den slik
        den er med innhold og signatur osv.»

        Lesepanelet viste `preview` — Odoos rene tekstutdrag, KUTTET på 140 tegn.
        Formatering, lenker og signatur forsvant, og lange e-poster endte midt i en
        setning. Testen lager en melding med HTML-signatur og krever at hele kommer med."""
        lang = "Hei Gjermund,<br/><br/>" + ("Detaljert avsnitt om leveransen. " * 20) + \
               "<br/><br/>--<br/><b>Kari Hansen</b><br/>Daglig leder<br/>" \
               "<a href='https://fiq.no'>fiq.no</a>"
        m = self.env["mail.message"].create({
            "subject": "TEST lang melding", "message_type": "email", "body": lang,
        })
        bt = self.Data.get_brodtekst(m.id)
        self.assertFalse(bt["tom"])
        self.assertGreater(len(bt["html"]), 140,
                           "hele meldingen skal med — ikke preview-utdraget på 140 tegn")
        self.assertIn("Kari Hansen", bt["html"], "signaturen må være med")
        self.assertIn("fiq.no", bt["html"], "lenker må overleve")

    def test_brodtekst_taaler_melding_uten_html(self):
        """Ren tekst uten HTML-kropp skal pakkes så linjeskift overlever."""
        m = self.env["mail.message"].create({
            "subject": "TEST", "message_type": "email", "body": "",
        })
        bt = self.Data.get_brodtekst(m.id)
        self.assertIsInstance(bt["html"], str)
        self.assertIn("tom", bt)

    def test_forhandsvisning_gir_url_ikke_innhold(self):
        """Store vedlegg skal ikke gjennom en RPC-runde bare for å vises."""
        a = self.env["ir.attachment"].create({"name": "d.pdf", "raw": b"%PDF-1.4",
                                              "mimetype": "application/pdf"})
        fv = self.Data.forhandsvis(a.id)
        self.assertIn("/web/content/%s" % a.id, fv["url"])
        self.assertTrue(fv["kan_vises"], "PDF skal kunne vises i nettleseren")
        self.assertNotIn("raw", fv)
