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
        self.assertTrue(
            set(tillatte).issubset(
                set(self.env.user.company_ids.ids) or set(self.env.company.ids)
            )
        )

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
        frist_utc = datetime.combine(siste, datetime.min.time()) + timedelta(
            hours=23, minutes=30
        )
        oppgave = self.env["project.task"].create(
            {
                "name": "TEST frist sent paa siste dag",
                "project_id": prosjekt.id,
                "user_ids": [(6, 0, self.env.user.ids)],
                "date_deadline": frist_utc,
            }
        )

        # Hvor HØRER den hjemme etter tidssone-konvertering? Spør Odoo, ikke gjett.
        lokal = fields.Datetime.context_timestamp(self.env["res.users"], frist_utc)
        forventet_dato = lokal.date()

        kal = self.Data.get_kalender(aar=forventet_dato.year, mnd=forventet_dato.month)
        navn = [
            h["navn"] for h in kal["dager"].get(forventet_dato.strftime("%Y-%m-%d"), [])
        ]
        self.assertIn(
            oppgave.name,
            navn,
            "fristen må ligge på datoen den har i BRUKERENS tidssone — "
            "faller den ut, er hentevinduet eller konverteringen feil",
        )

    def test_kalender_taaler_rart_argument_uten_aa_kaste(self):
        """🔴 KRASJET I NETTLESEREN 23.07: `t-on-click="aapneKalender"` sendte KLIKK-
        EVENTET som `aar`, og et event blir en DICT over RPC. `int(dict)` kastet
        TypeError — kallet returnerte HTTP 200 (Odoo pakker exceptionen i RPC-svaret),
        så INGEN ren -i-test fanget den. Flaten dør først i nettleseren.

        Denne testen kaller get_kalender som en klient KAN gjøre det — med et objekt —
        og krever at metoden RETURNERER, ikke bare at den finnes."""
        r = self.Data.get_kalender(aar={"onmousedown": True}, mnd=False, firm=False)
        self.assertIn(
            "dager", r, "et rart argument skal gi standardmåned, ikke exception"
        )
        # Ugyldig måned skal heller ikke sprenge date():
        r2 = self.Data.get_kalender(aar=2026, mnd=99, firm=False)
        self.assertIn("dager", r2)

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
            self.assertIn(
                p.id, [t["id"] for t in self.Data.sok_mal(p.sequence_code, "prosjekt")]
            )

    def test_par_melding_flytter_upart_melding(self):
        """`tildel()` kunne bare lage aktivitet på et element meldingen ALLEREDE
        hang på — den kunne ikke pare en upart melding. Det er hele poenget med
        paring, derfor `par_melding()`."""
        p = self.env["project.project"].create({"name": "TEST paringsmaal"})
        m = self.env["mail.message"].create(
            {
                "subject": "TEST upart melding",
                "message_type": "email",
                "body": "<p>test</p>",
            }
        )
        r = self.Data.par_melding(m.id, "project.project", p.id)
        self.assertTrue(
            r, "paring skal lykkes for et prosjekt brukeren har tilgang til"
        )
        m.invalidate_recordset()
        self.assertEqual(m.model, "project.project")
        self.assertEqual(m.res_id, p.id)

    def test_par_melding_avviser_ukjent_modell(self):
        """Kun prosjekt og oppgave er gyldige paringsmål."""
        m = self.env["mail.message"].create(
            {"subject": "TEST", "message_type": "email"}
        )
        self.assertFalse(
            self.Data.par_melding(m.id, "res.partner", self.env.user.partner_id.id)
        )

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
        m = self.env["mail.message"].create(
            {"subject": "TEST", "message_type": "email"}
        )
        self.assertFalse(self.Data.sett_tverr(m.id, "finnes_ikke"))

    def test_sett_tverr_lagres_og_kan_angres(self):
        """Overstyringen lagres med hvem og når, og tom verdi gir automatikk tilbake."""
        m = self.env["mail.message"].create(
            {"subject": "TEST", "message_type": "email"}
        )
        r = self.Data.sett_tverr(m.id, "haster")
        self.assertEqual(r["kode"], "haster")
        self.assertEqual(self.Data.get_thread(m.id)["tverr_kode"], "haster")
        self.assertTrue(
            self.Data.get_thread(m.id)["tverr_av"], "hvem som valgte skal vises"
        )
        self.Data.sett_tverr(m.id, "")
        self.assertEqual(
            self.Data.get_thread(m.id)["tverr_kode"],
            "",
            "tom verdi skal gi automatikken tilbake",
        )

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
        self.assertEqual(
            self.Data.gi_nytt_navn(a.id, "rapport.pdf")["navn"], "rapport.pdf"
        )

    def test_pdf_beholder_originalen(self):
        """Konvertering er IKKE erstatning — originalen skal bestå
        ([[fiq-vokter]] mist-aldri-innhold)."""
        a = self.env["ir.attachment"].create(
            {"name": "notat.txt", "raw": b"hei verden", "mimetype": "text/plain"}
        )
        r = self.Data.til_pdf(a.id)
        self.assertTrue(a.exists(), "originalen skal aldri slettes")
        if r.get("ok"):
            self.assertNotEqual(r["id"], a.id, "PDF-en skal være et NYTT vedlegg")
            self.assertTrue(r["navn"].endswith(".pdf"))

    def test_pdf_sier_ifra_om_ustoettet_format(self):
        """Ustøttet format skal gi en ærlig melding, ikke en tom fil."""
        a = self.env["ir.attachment"].create(
            {"name": "bilde.png", "raw": b"\x89PNG", "mimetype": "image/png"}
        )
        r = self.Data.til_pdf(a.id)
        self.assertFalse(r.get("ok"))
        self.assertTrue(r.get("feil"), "brukeren må få vite hvorfor")

    def test_brodtekst_gir_HELE_meldingen_ikke_utdrag(self):
        """Gjermund 23.07: «Selve mail teksten kommer dårlig frem. du må vise den slik
        den er med innhold og signatur osv.»

        Lesepanelet viste `preview` — Odoos rene tekstutdrag, KUTTET på 140 tegn.
        Formatering, lenker og signatur forsvant, og lange e-poster endte midt i en
        setning. Testen lager en melding med HTML-signatur og krever at hele kommer med."""
        lang = (
            "Hei Gjermund,<br/><br/>"
            + ("Detaljert avsnitt om leveransen. " * 20)
            + "<br/><br/>--<br/><b>Kari Hansen</b><br/>Daglig leder<br/>"
            "<a href='https://fiq.no'>fiq.no</a>"
        )
        m = self.env["mail.message"].create(
            {
                "subject": "TEST lang melding",
                "message_type": "email",
                "body": lang,
            }
        )
        bt = self.Data.get_brodtekst(m.id)
        self.assertFalse(bt["tom"])
        self.assertGreater(
            len(bt["html"]),
            140,
            "hele meldingen skal med — ikke preview-utdraget på 140 tegn",
        )
        self.assertIn("Kari Hansen", bt["html"], "signaturen må være med")
        self.assertIn("fiq.no", bt["html"], "lenker må overleve")

    def test_outlook_lenke_kun_naar_headeren_finnes(self):
        """«Åpne i Outlook» (Gjermund 23.07) bygger på e-postens RFC-header
        (`message_id`) — samme identifikator Outlook selv bruker.

        🛑 Knappen må IKKE vises for meldinger Outlook ikke kjenner: Odoo-genererte
        meldinger har en header Outlook aldri har sett, og interne notater har ingen.
        En død lenke er verre enn ingen knapp."""
        ekte = self.env["mail.message"].create(
            {
                "subject": "TEST ekte e-post",
                "message_type": "email",
                "body": "<p>hei</p>",
                "message_id": "<abc123@vidir.no>",
            }
        )
        self.assertTrue(
            self.Data.get_brodtekst(ekte.id)["outlook"],
            "e-post med RFC-header skal få Outlook-lenke",
        )

        notat = self.env["mail.message"].create(
            {
                "subject": "TEST internt notat",
                "message_type": "comment",
                "body": "<p>notat</p>",
            }
        )
        self.assertFalse(
            self.Data.get_brodtekst(notat.id)["outlook"],
            "interne notater finnes ikke i Outlook — ingen lenke",
        )

    # ---- Person-oversikt: ÉN person, ALL kommunikasjon ----------------------------

    def test_samme_person_samler_kontakt_dubletter(self):
        """🔴 KJERNEN i Gjermunds krav (etterlyst 14.07 OG 18.07): han finnes som 12
        kontakter i Production. Slår vi opp på ÉN partner-id, får han 12 halve
        historikker i stedet for hele bildet — og det ville sett riktig ut.

        Vi samler på e-postadresse, fordi det er koblingen som FAKTISK finnes i dataene."""
        a = self.env["res.partner"].create(
            {"name": "TEST Person A", "email": "same@fiq.no"}
        )
        b = self.env["res.partner"].create(
            {"name": "TEST Person B", "email": "SAME@fiq.no"}
        )
        samlet = self.Data._samme_person(a)
        self.assertIn(
            b.id,
            samlet.ids,
            "to kontakter med samme adresse ER samme menneske — også med ulik store bokstaver",
        )

    def test_uten_epost_gjettes_det_ALDRI_paa_navn(self):
        """🛑 To «Kari Hansen» kan være to mennesker. Mangler adressen, returneres kun
        kontakten selv — vi gjetter aldri på navn."""
        a = self.env["res.partner"].create({"name": "Kari Hansen"})
        self.env["res.partner"].create({"name": "Kari Hansen"})
        self.assertEqual(self.Data._samme_person(a).ids, [a.id])

    def test_person_kommunikasjon_gaar_BEGGE_veier(self):
        """«All kommunikasjon» er ikke bare innkommende — også det VI har sendt."""
        p = self.env["res.partner"].create(
            {"name": "TEST Motpart", "email": "motpart@x.no"}
        )
        self.env["mail.message"].create(
            {
                "subject": "TEST fra personen",
                "message_type": "email",
                "author_id": p.id,
                "body": "<p>hei</p>",
            }
        )
        self.env["mail.message"].create(
            {
                "subject": "TEST til personen",
                "message_type": "email",
                "partner_ids": [(6, 0, [p.id])],
                "body": "<p>svar</p>",
            }
        )
        r = self.Data.get_person_kommunikasjon(p.id)
        retninger = {m["retning"] for m in r["meldinger"]}
        self.assertIn("fra", retninger, "det personen sendte oss må være med")
        self.assertIn("til", retninger, "det vi sendte personen må være med")

    def test_person_kanaler_viser_kun_det_som_finnes(self):
        """🛑 En telefonknapp uten telefonnummer er en blindvei — nøyaktig problemet
        paringsfeltene hadde (knapper som så ut som funksjoner, men gjorde ingenting)."""
        uten = self.env["res.partner"].create({"name": "TEST uten data"})
        self.assertEqual(
            self.Data.get_person_kanaler(uten.id),
            [],
            "ingen kontaktdata → ingen kanalknapper",
        )
        # `mobile` finnes IKKE på res.partner i Odoo 19 (verifisert i
        # information_schema) — kun `phone`. Testen må bruke feltene som faktisk
        # finnes, ellers feiler den på MILJØET og ikke på koden.
        med = self.env["res.partner"].create(
            {"name": "TEST med data", "email": "a@b.no", "phone": "+47 900 00 000"}
        )
        koder = [k["kode"] for k in self.Data.get_person_kanaler(med.id)]
        self.assertIn("epost", koder)
        self.assertIn("telefon", koder)

    def test_brodtekst_taaler_melding_uten_html(self):
        """Ren tekst uten HTML-kropp skal pakkes så linjeskift overlever."""
        m = self.env["mail.message"].create(
            {
                "subject": "TEST",
                "message_type": "email",
                "body": "",
            }
        )
        bt = self.Data.get_brodtekst(m.id)
        self.assertIsInstance(bt["html"], str)
        self.assertIn("tom", bt)

    def test_forhandsvisning_gir_url_ikke_innhold(self):
        """Store vedlegg skal ikke gjennom en RPC-runde bare for å vises."""
        a = self.env["ir.attachment"].create(
            {"name": "d.pdf", "raw": b"%PDF-1.4", "mimetype": "application/pdf"}
        )
        fv = self.Data.forhandsvis(a.id)
        self.assertIn(f"/web/content/{a.id}", fv["url"])
        self.assertTrue(fv["kan_vises"], "PDF skal kunne vises i nettleseren")
        self.assertNotIn("raw", fv)

    # ---- AI-funksjonene (masterspec §C.6/§C.13, Gjermund 24.07) --------------------
    #
    # 🛑 Testene kaller ALDRI den ekte AI-tjenesten: den koster penger, krever nøkkel
    # og gir ulikt svar hver gang. Det som testes er VÅR logikk rundt kallet —
    # trådhenting, avkorting, opprydding av svaret og tilgangsvakten. Det er der
    # feilene våre bor; modellens formuleringer er ikke vårt ansvar.

    def test_ai_traad_henter_hele_kjeden_ikke_bare_meldingen(self):
        """«Sammendrag av mailkjede» må se HELE kjeden.

        Svar i Odoo henger på samme element, ikke nødvendigvis via parent_id. Ser vi
        bare på parent-kjeden, oppsummerer vi én melding og kaller det en tråd."""
        Ai = self.env["fiq.meldingssenter.ai"]
        prosjekt = self.env["project.project"].create({"name": "TEST AI-tråd"})
        laget = []
        for i in range(3):
            laget.append(
                self.env["mail.message"].create(
                    {
                        "subject": f"TEST kjede {i}",
                        "message_type": "email",
                        "model": "project.project",
                        "res_id": prosjekt.id,
                        "body": f"<p>melding {i}</p>",
                    }
                )
            )
        traad = Ai._traad_meldinger(laget[0].id)
        for m in laget:
            self.assertIn(m, traad, "alle meldinger på elementet hører til tråden")

    def test_ai_upart_melding_gir_bare_seg_selv(self):
        """En melding uten element har ingen kjede — da er den sin egen tråd.
        Uten dette ville `model`/`res_id` = False gitt et søk som traff ALT."""
        Ai = self.env["fiq.meldingssenter.ai"]
        m = self.env["mail.message"].create(
            {"subject": "TEST upart AI", "message_type": "email", "body": "<p>x</p>"}
        )
        traad = Ai._traad_meldinger(m.id)
        self.assertEqual(len(traad), 1)
        self.assertEqual(traad.id, m.id)

    def test_ai_lang_traad_avkortes_OG_SIER_IFRA(self):
        """🔴 Kjernen: et sammendrag som stille bygger på halve tråden er verre enn
        ingen sammendrag — leseren tror hun har fått med alt.

        Avkortingen i seg selv er riktig (lange tråder koster og treffer dårligere).
        Det som ikke er akseptabelt, er å gjøre det uten å si det."""
        Ai = self.env["fiq.meldingssenter.ai"]
        self.env["ir.config_parameter"].sudo().set_param(
            "fiq_gui_epost.ai_maks_tegn", "2000"
        )
        prosjekt = self.env["project.project"].create({"name": "TEST AI lang"})
        for i in range(12):
            self.env["mail.message"].create(
                {
                    "subject": f"TEST lang {i}",
                    "message_type": "email",
                    "model": "project.project",
                    "res_id": prosjekt.id,
                    "body": "<p>" + ("innhold " * 60) + "</p>",
                }
            )
        traad = Ai._traad_meldinger(
            self.env["mail.message"]
            .search([("model", "=", "project.project"), ("res_id", "=", prosjekt.id)])[
                0
            ]
            .id
        )
        tekst, utelatt = Ai._som_tekst(traad)
        self.assertTrue(utelatt, "med 2000 tegn og 12 lange meldinger MÅ noe utelates")
        self.assertIn(
            "utelatt",
            tekst,
            "avkortingen må stå i teksten AI-en leser — ellers oppsummerer den "
            "halve tråden som om den var hel",
        )

    def test_ai_sjekkliste_krever_skriverett_paa_oppgaven(self):
        """🛑 `res_id` kommer fra klienten. Uten tilgangssjekk kunne en gjettet id
        lagt punkter inn i et prosjekt brukeren ikke har noe med."""
        Ai = self.env["fiq.meldingssenter.ai"]
        self.assertFalse(
            Ai.lag_sjekkliste(999999999, ["TEST punkt"]),
            "ukjent oppgave skal gi False, ikke opprette noe",
        )

    def test_ai_sjekkliste_lagrer_ingenting_uten_punkter(self):
        """Tom liste = ingen deloppgaver. Et AI-svar kan være tomt, og da skal vi
        ikke lage en oppgave som heter ingenting."""
        Ai = self.env["fiq.meldingssenter.ai"]
        prosjekt = self.env["project.project"].create({"name": "TEST AI sjekkliste"})
        oppgave = self.env["project.task"].create(
            {"name": "TEST oppgave", "project_id": prosjekt.id}
        )
        self.assertFalse(Ai.lag_sjekkliste(oppgave.id, []))
        self.assertFalse(Ai.lag_sjekkliste(oppgave.id, ["   ", ""]))
        self.assertFalse(oppgave.child_ids, "ingen deloppgaver skal ha blitt laget")

    def test_ai_sjekkliste_legger_punkter_som_deloppgaver(self):
        """Sjekklista skal bruke Odoos EGEN mekanikk (deloppgaver), ikke en egen
        modell ved siden av — ellers skiller de to visningene lag."""
        Ai = self.env["fiq.meldingssenter.ai"]
        prosjekt = self.env["project.project"].create({"name": "TEST AI sjekkliste 2"})
        oppgave = self.env["project.task"].create(
            {"name": "TEST oppgave 2", "project_id": prosjekt.id}
        )
        r = Ai.lag_sjekkliste(oppgave.id, ["Punkt A", "Punkt B"])
        self.assertEqual(r["antall"], 2)
        navn = oppgave.child_ids.mapped("name")
        self.assertIn("Punkt A", navn)
        self.assertIn("Punkt B", navn)
        self.assertEqual(
            oppgave.child_ids[0].project_id,
            prosjekt,
            "deloppgaven må arve prosjektet — ellers havner den utenfor",
        )

    def test_ai_fritekst_uten_sporsmaal_kaller_ikke_tjenesten(self):
        """Tomt spørsmål skal ikke koste et AI-kall. Returnerer tom tekst uten å
        røre tjenesten — som ikke finnes i testmiljøet."""
        Ai = self.env["fiq.meldingssenter.ai"]
        m = self.env["mail.message"].create(
            {"subject": "TEST fritekst", "message_type": "email", "body": "<p>x</p>"}
        )
        self.assertEqual(Ai.fritekst(m.id, "")["tekst"], "")
        self.assertEqual(Ai.fritekst(m.id, "   ")["tekst"], "")

    # ---- Pinn (Gjermund 24.07: «et Pinn som hindrer at mailen forsvinner») ---------

    def test_pinn_er_personlig_ikke_felles(self):
        """🔑 En pinn betyr «JEG må ikke miste denne av syne». Var den felles, ville
        flaten fylles av andres påminnelser og funksjonen blitt ubrukelig."""
        m = self.env["mail.message"].create(
            {"subject": "TEST pinn", "message_type": "email", "body": "<p>x</p>"}
        )
        self.Data.sett_pinn(m.id, True)
        self.assertIn(m.id, self.Data._pinn_sett([m.id]))
        felt = self.env["fiq.meldingssenter.pinn"]._fields
        self.assertIn("user_id", felt, "pinnen MÅ bære hvem som satte den")

    def test_pinn_er_idempotent_begge_veier(self):
        """Knappen skal aldri kunne havne i utakt med det brukeren ser: å pinne noe
        som alt er pinnet — eller løsne noe som ikke er det — er ikke en feil."""
        m = self.env["mail.message"].create(
            {"subject": "TEST pinn 2", "message_type": "email", "body": "<p>x</p>"}
        )
        self.Data.sett_pinn(m.id, True)
        self.Data.sett_pinn(m.id, True)
        self.assertEqual(
            self.env["fiq.meldingssenter.pinn"].search_count(
                [("message_id", "=", m.id), ("user_id", "=", self.env.uid)]
            ),
            1,
            "to klikk skal ikke gi to rader",
        )
        self.Data.sett_pinn(m.id, False)
        self.Data.sett_pinn(m.id, False)
        self.assertNotIn(m.id, self.Data._pinn_sett([m.id]))

    def test_pinn_FOELGER_MED_naar_meldingen_tildeles_en_annen(self):
        """🔴 Gjermund 24.07: «pinnen bør følge med hvis e-posten tilegnes en annen
        bruker».

        Hvorfor dette ikke er en detalj: pinnen betyr «denne må ikke forsvinne i
        mengden». Overleveres saken, er det NETTOPP da den er i fare — den er ny for
        mottakeren og ligger blant hundre andre. Uten dette stoppet påminnelsen hos
        den som ga fra seg saken, og oppsto aldri hos den som overtok den."""
        prosjekt = self.env["project.project"].create({"name": "TEST pinn tildel"})
        m = self.env["mail.message"].create(
            {
                "subject": "TEST pinn følger",
                "message_type": "email",
                "model": "project.project",
                "res_id": prosjekt.id,
                "body": "<p>x</p>",
            }
        )
        mottaker = self.env["res.users"].create(
            {
                "name": "TEST Mottaker",
                "login": "fiq_test_pinn_mottaker",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.Data.sett_pinn(m.id, True)
        self.Data.tildel(m.id, mottaker.id)
        self.assertTrue(
            self.env["fiq.meldingssenter.pinn"]
            .sudo()
            .search_count([("message_id", "=", m.id), ("user_id", "=", mottaker.id)]),
            "mottakeren må ha fått pinnen — ellers stopper påminnelsen hos avgiveren",
        )

    def test_pinn_beholdes_hos_avgiver_ved_tildeling(self):
        """Vi FLYTTER ikke pinnen: avgiveren følger ofte saken videre, og å fjerne
        hens pinne ville vært å bestemme på hens vegne. Løsne er ett klikk."""
        prosjekt = self.env["project.project"].create({"name": "TEST pinn behold"})
        m = self.env["mail.message"].create(
            {
                "subject": "TEST pinn behold",
                "message_type": "email",
                "model": "project.project",
                "res_id": prosjekt.id,
                "body": "<p>x</p>",
            }
        )
        mottaker = self.env["res.users"].create(
            {
                "name": "TEST Mottaker 2",
                "login": "fiq_test_pinn_mottaker2",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.Data.sett_pinn(m.id, True)
        self.Data.tildel(m.id, mottaker.id)
        self.assertIn(
            m.id, self.Data._pinn_sett([m.id]), "avgiveren skal beholde sin egen pinne"
        )

    def test_upinnet_melding_gir_ingen_pinn_ved_tildeling(self):
        """Tildeling skal ikke FINNE PÅ en pinne. Var den ikke pinnet, er det ingen
        påminnelse å føre videre — da ville vi laget støy hos mottakeren."""
        prosjekt = self.env["project.project"].create({"name": "TEST upinnet"})
        m = self.env["mail.message"].create(
            {
                "subject": "TEST upinnet tildel",
                "message_type": "email",
                "model": "project.project",
                "res_id": prosjekt.id,
                "body": "<p>x</p>",
            }
        )
        mottaker = self.env["res.users"].create(
            {
                "name": "TEST Mottaker 3",
                "login": "fiq_test_pinn_mottaker3",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        self.Data.tildel(m.id, mottaker.id)
        self.assertFalse(
            self.env["fiq.meldingssenter.pinn"]
            .sudo()
            .search_count([("message_id", "=", m.id)]),
            "en upinnet melding skal ikke bli pinnet av at den tildeles",
        )

    # ---- Ta e-posten videre (Gjermund 24.07) ---------------------------------------

    def test_pdf_av_epost_tar_med_avsender_og_dato(self):
        """En arkivert e-post uten avsender og dato er ikke dokumentasjon, bare
        tekst. Hodet MÅ med i PDF-grunnlaget."""
        H = self.env["fiq.meldingssenter.handling"]
        p = self.env["res.partner"].create(
            {"name": "TEST Avsender PDF", "email": "pdf@x.no"}
        )
        m = self.env["mail.message"].create(
            {
                "subject": "TEST PDF-hode",
                "message_type": "email",
                "author_id": p.id,
                "body": "<p>selve teksten</p>",
                "date": fields.Datetime.now(),
            }
        )
        html = H._epost_som_html(m)
        self.assertIn("TEST Avsender PDF", html, "avsender må stå i arkivet")
        self.assertIn("TEST PDF-hode", html, "emnet må stå i arkivet")
        self.assertIn("selve teksten", html, "kroppen må være med")

    def test_pdf_krever_et_element_aa_feste_seg_paa(self):
        """En PDF som ikke havner noe sted er ikke arkivering."""
        H = self.env["fiq.meldingssenter.handling"]
        m = self.env["mail.message"].create(
            {
                "subject": "TEST PDF uten mål",
                "message_type": "email",
                "body": "<p>x</p>",
            }
        )
        r = H.epost_til_pdf(m.id)
        self.assertFalse(r["ok"])
        self.assertIn("prosjekt", r["feil"].lower())

    def test_sp_sier_NEI_naar_mappa_ikke_finnes(self):
        """🛑 Flaten spør FØR den viser «Lagre på SP» som valg. En knapp som alltid
        vises og noen ganger svarer «går ikke», er samme feil som de døde
        paringsfeltene: den ser ut som en funksjon.

        Målt 24.07: `fiq_dokument_sp_id` er IKKE installert i Production, så
        `sp_mappe_item_id` finnes ikke på project.task. Feature-deteksjonen er
        derfor nødvendig, ikke overforsiktig."""
        H = self.env["fiq.meldingssenter.handling"]
        prosjekt = self.env["project.project"].create({"name": "TEST SP"})
        oppgave = self.env["project.task"].create(
            {"name": "TEST SP-oppgave", "project_id": prosjekt.id}
        )
        r = H.sp_status("project.task", oppgave.id)
        self.assertFalse(r["klar"], "uten SP-mappe skal svaret være nei")
        self.assertTrue(r["grunn"], "og det skal stå HVORFOR, ikke bare «nei»")

    def test_oppgave_fra_epost_legger_mailen_i_LOGGEN(self):
        """🔑 Masterspec §C.6 er presis: «mailen i LOGGEN (ikke beskrivelsen)».

        I beskrivelsesfeltet blir e-posten redigerbar og mister avsender og dato —
        den slutter å være dokumentasjon på hva som faktisk ble sagt."""
        H = self.env["fiq.meldingssenter.handling"]
        prosjekt = self.env["project.project"].create({"name": "TEST oppgave fra mail"})
        p = self.env["res.partner"].create(
            {"name": "TEST Kunde mail", "email": "kunde@x.no"}
        )
        m = self.env["mail.message"].create(
            {
                "subject": "TEST henvendelse",
                "message_type": "email",
                "author_id": p.id,
                "body": "<p>kan dere hjelpe</p>",
            }
        )
        r = H.opprett_oppgave(m.id, prosjekt.id)
        self.assertTrue(r["ok"])
        oppgave = self.env["project.task"].browse(r["id"])
        self.assertEqual(oppgave.name, "TEST henvendelse")
        logg = oppgave.message_ids.mapped("body")
        self.assertTrue(
            any("kan dere hjelpe" in (b or "") for b in logg),
            "e-posten må ligge i loggen",
        )
        self.assertNotIn(
            "kan dere hjelpe",
            oppgave.description or "",
            "e-posten skal IKKE stå i beskrivelsen — der blir den redigerbar",
        )

    def test_oppgave_fra_epost_parer_meldingen_med_oppgaven(self):
        """Etter opprettelsen skal meldingen henge på den nye oppgaven — ellers
        står den fortsatt som «ikke paret» i lista."""
        H = self.env["fiq.meldingssenter.handling"]
        prosjekt = self.env["project.project"].create({"name": "TEST paring ny oppg"})
        m = self.env["mail.message"].create(
            {"subject": "TEST par ny", "message_type": "email", "body": "<p>x</p>"}
        )
        r = H.opprett_oppgave(m.id, prosjekt.id)
        m.invalidate_recordset()
        self.assertEqual(m.model, "project.task")
        self.assertEqual(m.res_id, r["id"])

    def test_oppgave_krever_prosjekt(self):
        """En oppgave uten prosjekt havner utenfor alt."""
        H = self.env["fiq.meldingssenter.handling"]
        m = self.env["mail.message"].create(
            {
                "subject": "TEST uten prosjekt",
                "message_type": "email",
                "body": "<p>x</p>",
            }
        )
        self.assertFalse(H.opprett_oppgave(m.id, 999999999)["ok"])

    def test_lead_oppretter_ALDRI_en_ny_kontakt(self):
        """En e-post er for tynt grunnlag til å lage en kunde av — det gir dubletter
        i kunderegisteret, og dublett-problemet er nettopp det person-oversikten
        finnes for å rydde opp i. Ukjent avsender → bare adressen."""
        H = self.env["fiq.meldingssenter.handling"]
        for_antall = self.env["res.partner"].search_count([])
        m = self.env["mail.message"].create(
            {
                "subject": "TEST lead ukjent",
                "message_type": "email",
                "email_from": "ukjent@ekstern.no",
                "body": "<p>tilbud?</p>",
            }
        )
        r = H.opprett_lead(m.id)
        self.assertTrue(r["ok"])
        self.assertEqual(
            self.env["res.partner"].search_count([]),
            for_antall,
            "det skal IKKE ha blitt opprettet en ny kontakt",
        )
        lead = self.env["crm.lead"].browse(r["id"])
        self.assertEqual(lead.email_from, "ukjent@ekstern.no")

    def test_lenke_FLYTTER_ikke_meldingen(self):
        """🔑 Forskjellen fra paring: paring flytter meldingen dit, og den forsvinner
        fra der den var. Noen ganger gjelder én e-post to steder — da er en lenke
        riktig svar, ikke en flytting."""
        H = self.env["fiq.meldingssenter.handling"]
        p1 = self.env["project.project"].create({"name": "TEST lenke hjem"})
        p2 = self.env["project.project"].create({"name": "TEST lenke mål"})
        m = self.env["mail.message"].create(
            {
                "subject": "TEST lenke",
                "message_type": "email",
                "model": "project.project",
                "res_id": p1.id,
                "body": "<p>x</p>",
            }
        )
        r = H.legg_lenke(m.id, "project.project", p2.id)
        self.assertTrue(r["ok"])
        m.invalidate_recordset()
        self.assertEqual(m.res_id, p1.id, "meldingen skal IKKE ha flyttet seg")
        self.assertTrue(
            any("TEST lenke" in (b or "") for b in p2.message_ids.mapped("body")),
            "lenken skal ligge i målets logg",
        )

    def test_lenke_avviser_modeller_vi_ikke_stotter(self):
        """Fail-closed: en modell vi ikke har vurdert, skal avvises — ikke prøves."""
        H = self.env["fiq.meldingssenter.handling"]
        m = self.env["mail.message"].create(
            {"subject": "TEST lenke feil", "message_type": "email", "body": "<p>x</p>"}
        )
        self.assertFalse(H.legg_lenke(m.id, "res.users", self.env.uid)["ok"])

    # ---- Søk med nn*nn (Gjermund 24.07) -------------------------------------------

    def test_nummersok_snevrer_inn_mens_du_skriver(self):
        """«en kortere og kortere liste etter hvert som du skriver»."""
        self.assertEqual(self.Data._nummerterm("25"), "25%")
        self.assertEqual(self.Data._nummerterm("25_0"), "25_0%")

    def test_nummersok_stjerne_er_brukerens_joker(self):
        """Gjermunds `nn*nn` — stjerne midt i nummeret."""
        self.assertEqual(self.Data._nummerterm("25*63"), "25%63%")

    def test_nummersok_taaler_BEGGE_skilletegn(self):
        """🔴 Målt i Production 24.07: nummereringen er IKKE konsistent — eldre
        prosjekter bruker «25_063», nyere «26-018». Skriver du bindestrek der basen
        har understrek, finner du ingenting, og du har ingen måte å vite hvilket
        skilletegn som gjelder for året ditt.

        `_` er SQL-joker for ett tegn, så begge skrivemåter treffer begge formene."""
        self.assertEqual(self.Data._nummerterm("26-018"), "26_018%")
        self.assertEqual(self.Data._nummerterm("25_063"), "25_063%")
        self.assertEqual(self.Data._nummerterm("26.018"), "26_018%")

    def test_nummersok_fjerner_prosent_fra_brukeren(self):
        """`%` er ikke et tegn i noe FIQ-nummer. Slapp den gjennom, ville et søk
        blitt til «vis alt» uten at brukeren skjønte hvorfor."""
        self.assertEqual(self.Data._nummerterm("25%"), "25%")

    def test_nummersok_bare_prosent_treffer_INGENTING(self):
        """🔴 Fanget da testen over ble skrevet: «%» alene blir tom streng etter
        strippingen, og «» + «%» er «vis alt» — stikk i strid med det stripping
        skulle oppnå. En vakt som slår tilbake til det den skulle hindre."""
        self.assertNotIn(
            self.Data._nummerterm("%"),
            ("%", ""),
            "bare-prosent skal aldri bli et mønster som treffer alt",
        )

    # ---- Dekning av `mail_message_search_global` (konsolidering, modul 1) ----------
    #
    # Modulen har ÉN metode — `action_open_related()` — som bygger en act_window mot
    # (message.model, message.res_id). Testfila er TOM (0 byte), så det finnes ingen
    # fasit fra dens side; testene under er fasiten vi lager før noe fjernes.
    #
    # 🛑 Kravet fra AI IQ er dekning, ikke likhet: min `aapneFraPerson()` må håndtere
    # de tilfellene originalen håndterer FEIL — ikke bare de den håndterer likt.
    # Målt i Production 24.07: 233 av 44 634 meldinger har res_id = 0, og 230 av dem
    # har model = False. Kanten er ekte data, ikke et tenkt tilfelle.

    def test_upart_melding_gir_IKKE_en_aapne_handling(self):
        """🔴 Kjernen i dekningsbeviset.

        `action_open_related()` bygger act_window UANSETT — også når model er False og
        res_id er 0. Odoo får da `res_model: False` og svarer med en feilside.
        Målt i Production: 230 meldinger ville gjort nettopp det.

        Min side leverer `element`/`res_id` som tomme for slike meldinger, og
        `aapneFraPerson()` åpner kun når BEGGE finnes (epost.js:585). Resultatet er at
        raden ikke er klikkbar — ikke at klikket feiler."""
        p = self.env["res.partner"].create(
            {"name": "TEST Upart", "email": "upart@x.no"}
        )
        self.env["mail.message"].create(
            {
                "subject": "TEST uten tilknytning",
                "message_type": "email",
                "author_id": p.id,
                "body": "<p>ingen model, ingen res_id</p>",
            }
        )
        r = self.Data.get_person_kommunikasjon(p.id)
        traff = [m for m in r["meldinger"] if m["emne"] == "TEST uten tilknytning"]
        self.assertTrue(traff, "meldingen skal fortsatt VISES i historikken")
        self.assertFalse(
            traff[0].get("element") and traff[0].get("res_id"),
            "en melding uten tilknytning skal ikke gi noe å åpne — "
            "det er nettopp her originalen bygger en act_window mot ingenting",
        )

    def test_paret_melding_gir_element_og_res_id(self):
        """Den andre halvdelen: der originalen gjør noe fornuftig, må min gjøre det
        samme. Er meldingen paret, skal vi få nøyaktig (model, res_id) — det er de
        to verdiene `action_open_related()` bygger sin act_window av."""
        p = self.env["res.partner"].create(
            {"name": "TEST Paret", "email": "paret@x.no"}
        )
        prosjekt = self.env["project.project"].create({"name": "TEST Prosjekt paring"})
        self.env["mail.message"].create(
            {
                "subject": "TEST paret melding",
                "message_type": "email",
                "author_id": p.id,
                "model": "project.project",
                "res_id": prosjekt.id,
                "body": "<p>hei</p>",
            }
        )
        r = self.Data.get_person_kommunikasjon(p.id)
        traff = [m for m in r["meldinger"] if m["emne"] == "TEST paret melding"]
        self.assertTrue(traff, "den parede meldingen må være i historikken")
        self.assertEqual(traff[0]["element"], "project.project")
        self.assertEqual(traff[0]["res_id"], prosjekt.id)

    def test_slettet_element_gir_ikke_en_doed_lenke(self):
        """Meldingen overlever elementet den peker på: `mail.message` har ingen
        fremmednøkkel mot (model, res_id), så sletter noen prosjektet, blir res_id
        stående og peker i tomme luften.

        `action_open_related()` bygger act_window mot den slettede id-en → feilside.
        Min side skal ikke tilby en lenke som ikke fører noe sted."""
        p = self.env["res.partner"].create(
            {"name": "TEST Slettet", "email": "slettet@x.no"}
        )
        prosjekt = self.env["project.project"].create({"name": "TEST Slettes"})
        pid = prosjekt.id
        self.env["mail.message"].create(
            {
                "subject": "TEST peker paa slettet",
                "message_type": "email",
                "author_id": p.id,
                "model": "project.project",
                "res_id": pid,
                "body": "<p>hei</p>",
            }
        )
        prosjekt.unlink()
        r = self.Data.get_person_kommunikasjon(p.id)
        traff = [m for m in r["meldinger"] if m["emne"] == "TEST peker paa slettet"]
        self.assertTrue(traff, "meldingen finnes fortsatt selv om elementet er borte")
        self.assertFalse(
            self.env["project.project"].browse(pid).exists(),
            "forutsetningen for testen: elementet SKAL være slettet",
        )
        self.assertFalse(
            traff[0].get("res_id"),
            "en peker til et slettet element skal ikke bli en klikkbar lenke",
        )
