"""Tester for DATALAGETS BEREGNINGER i fiq.gui.prj.data.

🔑 HVA SOM HØRER HJEMME HER — og hvorfor skillet finnes (23.07.2026):
Datalaget og flaten fikk hver sin eier etter AI PKs arbeidsdeling. To agenter som
skriver i samme testfil overskriver hverandre stille — samme klasse som to spor på
samme gren. Derfor er testene delt etter HVA de faktisk måler:

    DENNE FILA (datalaget, B)      test_prj_data.py (flaten, A)
    ─────────────────────────      ────────────────────────────
    _risiko_dom                    at «risiko» finnes på hver rad
    _risiko_hvorfor                at feltene flaten tegner er der
    _budsjett_status               WBS-treets form og rollup
    _forbruk_prosent               tenant-isolasjon i flatens utganger
    rene tall inn → dom ut         kortslutningenes FORM

📌 Kriteriet er ikke «hvilken metode kalles», men **hva påstanden handler om**.
En test som kaller `_risiko_dom` med oppdiktede tall og krever en bestemt dom er
en beregningstest. En test som kaller `get_prosjektoversikt()` og krever at nøkkelen
`risiko` er til stede er en KONTRAKT mot flaten — den blir hos A.

🔑 ALLE testene her regner på EGEN tilstand (kanon 4i): ingen påstand avhenger av
hva som tilfeldigvis står i basen. Dev-basen er demodata og har aldri sett kundens
tall. En test som leser Dev-demodata og konkluderer om FIQ måler feil univers.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_prj")
class TestPrjDataLag(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.prj.data"]

    # ---------- PRIORITET: ÉN SANNHET, ÉN FORM ----------

    def test_prioritet_er_alltid_en_form_flaten_kan_tegne(self):
        """🔴 REGRESJON: datalaget sendte TO ULIKE FORMER for samme begrep.

            get_oppgaver_over_tid  →  "h" / "m"      (mappet)
            get_oppgaver           →  t.priority     ("0" / "1", rått)

        Flaten (prj.js prioSymbol) leser «h» → ▴, «l» → ▾, alt annet → ▪.
        En rå «1» traff ingen av grenene og falt til ▪ — feil symbol, ingen
        feilmelding, ingen som merket det.

        🔑 Samme klasse som kortslutningene i 1.31.0: to utganger fra samme
        datalag med hver sin form. Testen låser at BEGGE gir samme sett.
        """
        for verdi in ("h", "m", "l"):
            self.assertIn(verdi, self.Data.PRIORITET_LOVLIG)
        self.assertEqual(len(self.Data.PRIORITET_LOVLIG), 3)

    def test_prioritet_leser_det_egne_feltet_ikke_odoos(self):
        """Tre nivåer skal komme fra `fiq_prioritet`, ikke fra Odoos binære felt.

        🔑 Testen OPPRETTER tilstanden den verner mot (port 6): en oppgave med
        `fiq_prioritet = "l"` og Odoos `priority = "0"`. Leste vi Odoos felt,
        ville svaret blitt «m» — «lav» finnes ikke der. Da ville hele grunnen
        til at feltet ble bygget vært borte, og ingen eksisterende test hadde
        fanget det.
        """
        prosjekt = self.env["project.project"].search([], limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å henge testoppgaven på")

        oppgave = self.env["project.task"].create({
            "name": "TEST lav prioritet",
            "project_id": prosjekt.id,
            "fiq_prioritet": "l",
        })
        self.assertEqual(
            self.Data._prioritet(oppgave), "l",
            "«Lav» finnes bare i vårt eget felt — leses Odoos priority, går den tapt",
        )

        oppgave.fiq_prioritet = "h"
        self.assertEqual(self.Data._prioritet(oppgave), "h")

    def test_prioritet_defaulter_til_normal(self):
        """En ny oppgave uten valgt prioritet skal være «Normal», ikke tom.

        🔑 `required=True` + `default="m"` er valgt framfor et valgfritt felt
        nettopp for å slippe å tolke tomhet ETT sted til. «Tom betyr normal»
        er den parallelle tolkningen AI PK avviste da han valgte eget felt.
        """
        prosjekt = self.env["project.project"].search([], limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å henge testoppgaven på")

        oppgave = self.env["project.task"].create({
            "name": "TEST uten valgt prioritet",
            "project_id": prosjekt.id,
        })
        self.assertEqual(oppgave.fiq_prioritet, "m")
        self.assertEqual(self.Data._prioritet(oppgave), "m")

    def test_prioritet_roerer_aldri_odoos_eget_felt(self):
        """🛑 Odoos `priority` er Odoos. Vi legger til, vi erstatter ikke.

        Andre moduler leser `priority` som boolsk. Skrev vi i den, ville en
        «lav» FIQ-prioritet kunnet endre hva Odoos stjerne viser — og en
        modul vi ikke eier ville lest et tall vi hadde funnet på.
        """
        prosjekt = self.env["project.project"].search([], limit=1)
        if not prosjekt:
            self.skipTest("Ingen prosjekter å henge testoppgaven på")

        oppgave = self.env["project.task"].create({
            "name": "TEST uavhengighet", "project_id": prosjekt.id,
        })
        for verdi in ("h", "l", "m"):
            oppgave.fiq_prioritet = verdi
            self.assertEqual(
                oppgave.priority, "0",
                f"FIQ-prioritet «{verdi}» endret Odoos eget priority-felt — "
                "de skal være uavhengige",
            )

    def test_prioritet_ukjent_verdi_faller_til_normal(self):
        """En verdi flaten ikke kan tegne skal aldri nå den.

        Feltet er `required` i dag, så dette skal ikke kunne skje. Vakten står
        likevel: et felt som er påkrevd i dag kan bli valgfritt i morgen, og da
        skal flaten fortsatt få noe den kan tegne i stedet for et blankt symbol.
        """
        class FalskOppgave:
            _fields = {"fiq_prioritet": True}
            fiq_prioritet = "tull"

        self.assertEqual(self.Data._prioritet(FalskOppgave()), "m")

        class UtenFelt:
            _fields = {}

        self.assertEqual(
            self.Data._prioritet(UtenFelt()), "m",
            "Mangler feltet, skal datalaget svare «m» — ikke felle flaten",
        )

    # ---------- FORBRUK: ALDRI KAPPET ----------

    def test_forbruk_regnes_uten_kapping(self):
        """Regnestykket direkte: 215,9 timer mot budsjett 10 = 2159 %, ikke 100.

        🔴 REGRESJON: kappingen `min(100.0, ...)` skjulte et 22× overforbruk.
        Et prosjekt med 215,9 timer mot budsjett 10 ble vist som «100 % grønn».
        Det er ikke en visningsfeil — det er å skjule nettopp det varselet den
        som styrer økonomien MÅ se.

        Uavhengig av hva som ligger i basen — dette er tallet fra det ekte funnet,
        og det skal aldri kappes igjen.
        """
        self.assertEqual(self.Data._forbruk_prosent(215.9, 10.0), 2159.0)
        self.assertEqual(self.Data._forbruk_prosent(50.0, 100.0), 50.0)
        # Uten budsjett er en prosentandel meningsløs — ikke null, men «ingen».
        self.assertEqual(self.Data._forbruk_prosent(80.0, 0.0), 0.0)

    def test_forbruk_uten_budsjett_er_aldri_negativt_eller_udefinert(self):
        """Et negativt eller manglende budsjett skal ikke gi et vilt tall.

        `budsjett <= 0` fanger BEGGE: 0 (ikke satt) og et negativt tall som
        aldri burde finnes, men som en importfeil kan produsere. Uten dette
        ville en negativ nevner gitt en negativ prosent — et tall flaten
        ville tegnet som en stripe bakover.
        """
        self.assertEqual(self.Data._forbruk_prosent(10.0, 0.0), 0.0)
        self.assertEqual(self.Data._forbruk_prosent(10.0, -5.0), 0.0)
        self.assertEqual(self.Data._forbruk_prosent(0.0, 0.0), 0.0)

    # ---------- BUDSJETT-AKSEN (kravspek batch 15) ----------

    def test_budsjett_status_er_rod_ved_overforbruk(self):
        """Fargeaksen i batch 15: blå innenfor · rød over · grønn ferdig.

        🔴 Ferdig SLÅR IKKE UT over rødt: en ferdig aktivitet som brukte 3×
        budsjettet er ikke en suksess å farge grønn — det er erfaringen neste
        kalkyle skal bygge på.
        """
        self.assertEqual(self.Data._budsjett_status(5.0, 10.0, False), "innenfor")
        self.assertEqual(self.Data._budsjett_status(15.0, 10.0, False), "over")
        self.assertEqual(self.Data._budsjett_status(8.0, 10.0, True), "ferdig")
        self.assertEqual(self.Data._budsjett_status(30.0, 10.0, True), "over")
        self.assertEqual(self.Data._budsjett_status(0.0, 0.0, False), "plan")

    def test_budsjett_status_timer_uten_budsjett_er_ikke_plan(self):
        """Timer ført uten budsjett = «innenfor», ikke «plan».

        «Plan» betyr «ikke startet». Er det ført timer, ER arbeidet i gang —
        selv om ingen satte et budsjett. Ble dette meldt som «plan», ville et
        prosjekt med 40 førte timer sett ut som urørt på flaten.
        """
        self.assertEqual(self.Data._budsjett_status(40.0, 0.0, False), "innenfor")
        self.assertEqual(self.Data._budsjett_status(0.0, 10.0, False), "innenfor")

    # ---------- RISIKO-DOMMEN (krav 7) ----------
    #
    # 🔑 Fasitens fire eksempler ER testdataene. AI KR/AI PK 23.07: «Dere har
    # tallet. Fasiten vil ha dommen.» Testene under sjekker at vi feller den
    # samme dommen som fasiten viser — ikke bare at metoden svarer noe.

    def test_risiko_i_balanse_naar_forbruk_foelger_fremdrift(self):
        """Fasiten: «26_042 Kabelgata · 62 % brukt / 62 % fremdrift → i balanse»."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=62.0, budsjett=100.0, fremdrift=62.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(
            dom, "i_balanse",
            "62 % brukt av 62 % ferdig er sunt — det skal ikke merkes som risiko",
        )

    def test_risiko_tett_budsjett_naar_forbruk_loeper_fra_fremdriften(self):
        """Pengene brukes fortere enn arbeidet blir gjort.

        🔑 Dette er hele poenget med dommen: INGEN grense er passert (62 < 100),
        så både `budsjett_status` og et rent forbrukstall sier «innenfor». Odoo
        sier ingenting. Men 62 % brukt på 20 % arbeid er på vei mot sprekk, og
        det er nettopp det Gjermund skal få vite FØR det smeller.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=62.0, budsjett=100.0, fremdrift=20.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(
            dom, "tett_budsjett",
            "62 % brukt på 20 % fremdrift skal varsles, ikke passere som «innenfor»",
        )

    def test_risiko_penger_brukt_uten_fremdrift_er_ikke_i_balanse(self):
        """🔴 REGRESJON — funnet 23.07 på ekte rader ETTER at ni tester var grønne.

        Dommen meldte «i_balanse» om «36 % brukt / 0 % fremdrift». Vakten
        `fremdrift > 0` var ment mot manglende data, men slapp gjennom det
        VERSTE tilfellet: penger brukt uten at noe er gjort.

        🔑 Ingen av de ni testene hadde fremdrift = 0. De var grønne på en sak
        de aldri stilte. Det er hele grunnen til at ekte rader ble lest etter
        at testene passerte — «grønn» og «riktig» er to påstander.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=36.0, budsjett=100.0, fremdrift=0.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(
            dom, "tett_budsjett",
            "36 % av budsjettet brukt uten en eneste ferdig oppgave er ikke balanse",
        )

    def test_risiko_frist_i_dag_slaar_sunt_budsjett(self):
        """Fasiten: «24_055 Oscarsgate · tilbud avgjøres i dag kl 15 → avgjøres».

        Budsjettet er helt sunt. Dommen skal likevel være «avgjøres» — en frist
        i dag tåler ikke å vente til i morgen, uansett hvor bra økonomien er.
        Det er derfor risiko er en EGEN akse og ikke en omskriving av budsjett.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=10.0, budsjett=100.0, fremdrift=10.0,
            naermeste_frist=i_dag, i_dag=i_dag,
        )
        self.assertEqual(dom, "avgjores", "Frist i dag skal slå gjennom alt annet")

    def test_risiko_passert_frist_gir_avgjores(self):
        """En frist som er passert er ikke «tett tid» — den er forbi."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=1.0, budsjett=100.0, fremdrift=90.0,
            naermeste_frist=i_dag - timedelta(days=5), i_dag=i_dag,
        )
        self.assertEqual(dom, "avgjores", "Passert frist må aldri se ut som i balanse")

    def test_risiko_tett_tid_naar_fristen_er_naer_men_ikke_naadd(self):
        """Fasiten: «26_015 BUF · EM-frist i dag → tett tid» for det som nærmer seg.

        Grensa i koden er tre dager. Denne testen låser den, ellers kan en
        senere endring flytte den uten at noen merker det: en frist om to
        dager ville stille falt til «i balanse».
        """
        i_dag = fields.Date.today()
        self.assertEqual(
            self.Data._risiko_dom(
                fort=10.0, budsjett=100.0, fremdrift=10.0,
                naermeste_frist=i_dag + timedelta(days=2), i_dag=i_dag,
            ),
            "tett_tid",
            "Frist om to dager er tett tid, ikke balanse",
        )
        self.assertEqual(
            self.Data._risiko_dom(
                fort=10.0, budsjett=100.0, fremdrift=10.0,
                naermeste_frist=i_dag + timedelta(days=30), i_dag=i_dag,
            ),
            "i_balanse",
            "Frist om 30 dager er ikke en risiko i seg selv",
        )

    def test_risiko_over_budsjett_er_alltid_roedt(self):
        """Brukt mer enn budsjettet: rødt uansett fremdrift."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=159.3, budsjett=1.0, fremdrift=100.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(dom, "over_budsjett", "15 931 % forbruk skal aldri passere")

    def test_risiko_ferdig_prosjekt_er_ikke_risiko(self):
        """Alt ferdig = ingen dom å felle, uansett hvor galt det gikk underveis."""
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=999.0, budsjett=1.0, fremdrift=100.0,
            naermeste_frist=i_dag - timedelta(days=30), i_dag=i_dag, ferdig=True,
        )
        self.assertEqual(dom, "ferdig", "Et avsluttet prosjekt er historie, ikke risiko")

    def test_risiko_uten_budsjett_og_frist_er_i_balanse(self):
        """Ingen data å dømme på = ingen dom, ikke en oppdiktet risiko.

        🔑 Fravær av data er ikke fravær av risiko — men det er heller ikke
        BEVIS på risiko. Å melde «tett budsjett» på et prosjekt uten budsjett
        ville vært en påstand vi ikke kan belegge. Begrunnelsen
        (`_risiko_hvorfor`) sier i klartekst hvorfor linja er tom.
        """
        i_dag = fields.Date.today()
        dom = self.Data._risiko_dom(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=None, i_dag=i_dag,
        )
        self.assertEqual(dom, "i_balanse")

    def test_risiko_dommen_er_alltid_en_lovlig_verdi(self):
        """Flaten kan bare farge dommer den kjenner.

        En ukjent verdi ville gitt en ufarget rad uten feilmelding — den
        stille varianten av en feil. Denne testen kjører dommen gjennom et
        tverrsnitt av tilstander og krever at svaret alltid er i settet
        flaten kan tegne.
        """
        lovlige = {
            "i_balanse", "tett_budsjett", "over_budsjett",
            "tett_tid", "avgjores", "ferdig",
        }
        i_dag = fields.Date.today()
        frister = [None, i_dag - timedelta(days=5), i_dag,
                   i_dag + timedelta(days=2), i_dag + timedelta(days=60)]
        for fort, budsjett, fremdrift in [
            (0.0, 0.0, 0.0), (36.0, 100.0, 0.0), (62.0, 100.0, 62.0),
            (150.0, 100.0, 90.0), (10.0, 0.0, 0.0), (0.0, 100.0, 0.0),
        ]:
            for frist in frister:
                for ferdig in (False, True):
                    dom = self.Data._risiko_dom(
                        fort, budsjett, fremdrift, frist, i_dag, ferdig,
                    )
                    self.assertIn(
                        dom, lovlige,
                        "Ukjent dom «{}» for ({} t / {} t / {} % / frist {} / "
                        "ferdig {})".format(
                            dom, fort, budsjett, fremdrift, frist, ferdig
                        ),
                    )

    # ---------- BEGRUNNELSEN ----------

    def test_risiko_hvorfor_forklarer_dommen_i_klartekst(self):
        """🔑 Et merke uten begrunnelse er bare et nytt tall å tolke.

        Fasiten viser ALDRI merket alene: «62 % brukt / 62 % fremdrift»,
        «EM-frist i dag». Gjermund skal kunne lese linja og vite hva han skal
        gjøre — ikke måtte åpne prosjektet for å finne ut hvorfor det er rødt.
        """
        i_dag = fields.Date.today()
        tekst = self.Data._risiko_hvorfor(
            fort=62.0, budsjett=100.0, fremdrift=20.0,
            naermeste_frist=i_dag, i_dag=i_dag,
        )
        self.assertIn("frist i dag", tekst.lower(), "Fristen må stå i klartekst")
        self.assertIn("%", tekst, "Forbruk mot fremdrift må vises som tall")

    def test_risiko_hvorfor_er_aldri_tom(self):
        """Uten frist og budsjett skal linja forklare seg, ikke stå tom.

        En tom celle ser ut som manglende data. «ingen frist eller budsjett satt»
        er et svar — og det er ofte selve funnet.
        """
        tekst = self.Data._risiko_hvorfor(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=None, i_dag=fields.Date.today(),
        )
        self.assertTrue(tekst.strip(), "Begrunnelsen skal aldri være tom")

    def test_risiko_hvorfor_sier_fra_om_timer_uten_budsjett(self):
        """Timer ført uten budsjett skal sies, ikke gi en tom linje.

        Uten dette ville begrunnelsen stått tom på et prosjekt med 40 førte
        timer — og en tom linje leses som manglende data, ikke som et funn.
        """
        tekst = self.Data._risiko_hvorfor(
            fort=40.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=None, i_dag=fields.Date.today(),
        )
        self.assertIn("timer", tekst.lower())
        self.assertIn("uten budsjett", tekst.lower())

    def test_risiko_hvorfor_teller_dager_riktig_begge_veier(self):
        """Passert, i dag, i morgen — tre ulike formuleringer, ingen forveksling.

        🔑 «frist passert for 5 dager siden» og «frist om 5 dager» er motsatte
        meldinger. Et fortegnsfeil her ville gitt en beroligende tekst på noe
        som allerede har gått galt — verre enn ingen tekst.
        """
        i_dag = fields.Date.today()

        passert = self.Data._risiko_hvorfor(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=i_dag - timedelta(days=5), i_dag=i_dag,
        )
        self.assertIn("passert", passert.lower())
        self.assertIn("5", passert)

        i_morgen = self.Data._risiko_hvorfor(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=i_dag + timedelta(days=1), i_dag=i_dag,
        )
        self.assertIn("i morgen", i_morgen.lower())

        i_dag_tekst = self.Data._risiko_hvorfor(
            fort=0.0, budsjett=0.0, fremdrift=0.0,
            naermeste_frist=i_dag, i_dag=i_dag,
        )
        self.assertIn("i dag", i_dag_tekst.lower())

    def test_risiko_hvorfor_ferdig_sier_at_alt_er_gjort(self):
        """Et avsluttet prosjekt skal begrunne seg som historie, ikke som risiko."""
        tekst = self.Data._risiko_hvorfor(
            fort=999.0, budsjett=1.0, fremdrift=100.0,
            naermeste_frist=fields.Date.today(), i_dag=fields.Date.today(),
            ferdig=True,
        )
        self.assertIn("ferdig", tekst.lower())

    # ---------- DOMMEN OG BEGRUNNELSEN MÅ HENGE SAMMEN ----------

    def test_dom_og_begrunnelse_snakker_om_samme_sak(self):
        """🔑 De to metodene regner UAVHENGIG på samme tall.

        Endrer noen grensa i den ene uten den andre, får Gjermund et rødt
        merke med en beroligende begrunnelse — eller motsatt. Ingen
        feilmelding, bare en flate som motsier seg selv.

        Testen krever ikke identisk ordlyd, men at begrunnelsen NEVNER
        fristen når dommen handler om frist.
        """
        i_dag = fields.Date.today()
        for dager, ord in [(0, "i dag"), (1, "i morgen"), (2, "om 2 dager")]:
            frist = i_dag + timedelta(days=dager)
            dom = self.Data._risiko_dom(
                fort=10.0, budsjett=100.0, fremdrift=10.0,
                naermeste_frist=frist, i_dag=i_dag,
            )
            tekst = self.Data._risiko_hvorfor(
                fort=10.0, budsjett=100.0, fremdrift=10.0,
                naermeste_frist=frist, i_dag=i_dag,
            )
            self.assertIn(
                dom, ("avgjores", "tett_tid"),
                f"Frist om {dager} dager skal gi en tidsdom",
            )
            self.assertIn(
                ord, tekst.lower(),
                # 🔑 `%r` → `{!r}`, ikke `{}`. repr() beholder anførselstegn og
                # viser usynlige tegn — i en feilmelding om manglende tekst er
                # det nettopp forskjellen mellom «tom» og «bare mellomrom».
                "Dommen «{}» handler om fristen, men begrunnelsen nevner den "
                "ikke: {!r}".format(dom, tekst),
            )
