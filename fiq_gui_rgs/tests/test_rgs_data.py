# -*- coding: utf-8 -*-
"""Tester for Regnskapsflatens datalag (fiq.gui.rgs.data).

Hvorfor de finnes: flaten viser BOKFØRTE tall som er juridisk bindende. En feil her
er ikke en kosmetisk bug — den er et galt regnskapstall foran daglig leder.

PORT 6-disiplin: hver test OPPRETTER sin egen tilstand. En test som bare leser
eksisterende data kan ikke bevise fravær av data-betingede krasj — 42 grønne tester
på tom base skjulte en TypeError som felte hele flaten (Prosjekt 21.07).

Testene her speiler ekte datamønstre fra Staging 19.07: forfalte fakturaer opptil
1248 dager gamle, kreditnotaer, og bilag som er betalt (amount_residual = 0).
"""

from odoo import api, fields
from odoo.tests import TransactionCase, tagged


# 🛑 `fiq`-taggen er PÅKREVD (kanon 24.07): CI-gaten i `apps-ai` plukker tester
# på den. Uten den hoppes hele klassen over — og gaten melder grønt uten at én
# test kjørte. Det var nettopp slik gaten sto åpen etter domeneinndelingen.
# `fiq_rgs` beholdes som mer spesifikt filter for kjøring av kun dette sporet.
@tagged("post_install", "-at_install", "fiq", "fiq_rgs")
class TestRgsData(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.rgs.data"]
        cls.Move = cls.env["account.move"]
        cls.i_dag = fields.Date.context_today(cls.Data)

        cls.kunde = cls.env["res.partner"].create({"name": "FIQ Testkunde AS"})
        cls.produkt = cls.env["product.product"].create({
            "name": "FIQ Testtjeneste",
            "type": "service",
        })

    @classmethod
    def _faktura(cls, dager_til_forfall, belop=1000.0, type_="out_invoice", bokfor=True):
        """Oppretter EN faktura med kjent forfall. Negativ = forfalt."""
        forfall = fields.Date.add(cls.i_dag, days=dager_til_forfall)
        faktura = cls.Move.create({
            "move_type": type_,
            "partner_id": cls.kunde.id,
            "invoice_date": cls.i_dag,
            "invoice_date_due": forfall,
            "invoice_line_ids": [(0, 0, {
                "product_id": cls.produkt.id,
                "quantity": 1,
                "price_unit": belop,
                "tax_ids": [(6, 0, [])],  # uten mva — testen måler beløp, ikke avgift
            })],
        })
        if bokfor:
            faktura.action_post()
        return faktura

    # ---------- KUN BOKFØRTE TALL ----------

    def test_kladd_teller_ikke(self):
        """🔴 KRITISK: en kladd er IKKE bokført og skal aldri inn i et likviditetsbilde.

        Rollens regel: «ALDRI gjett — regnskap er juridisk bindende.» Et ubokført
        bilag som teller med, viser penger som juridisk sett ikke finnes.
        """
        for_ = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self._faktura(-10, belop=50000.0, bokfor=False)  # kladd
        etter = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self.assertEqual(for_, etter, "Kladd skal ikke telle med i ubetalt")

    def test_bokfort_teller(self):
        """Motstykket: en bokført, ubetalt faktura SKAL telle."""
        for_ = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self._faktura(-10, belop=1234.0)
        etter = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self.assertAlmostEqual(etter - for_, 1234.0, places=2)

    # ---------- BØTTENE SKILLER RIKTIG ----------

    def test_kritisk_er_forfalt_haster_er_ikke(self):
        """🔴 REGRESJON: «haster» og «kritisk» må ikke blandes.

        haster = forfaller innen 7 dager, IKKE forfalt ennå
        kritisk = allerede forfalt
        Blandes de, mister daglig leder skillet mellom «følg med» og «gjør noe nå».
        """
        self._faktura(-30, belop=5000.0)   # forfalt → kritisk
        self._faktura(3, belop=7000.0)     # forfaller om 3 dager → haster
        self._faktura(60, belop=9000.0)    # langt fram → ingen av delene

        b = {x["key"]: x["verdi"] for x in self.Data.hent_grunnbilde()["botter"]}
        self.assertGreaterEqual(b["kritisk"], 5000.0, "Forfalt skal være kritisk")
        self.assertGreaterEqual(b["haster"], 7000.0, "Forfall om 3 dager skal haste")
        self.assertNotIn(9000.0, [b["haster"], b["kritisk"]],
                         "Forfall om 60 dager er hverken haster eller kritisk")

    def test_betaling_uten_avstemming_teller_fortsatt(self):
        """🔴 EKTE BEGRENSNING, ikke en bug — målt 22.07 på Dev OG fiqas Production.

        Erstatter `test_betalt_faktura_teller_ikke` (Finans 2.70). Den bygget på
        antakelsen at Odoos betalingsveiviser gir `paid`. Antakelsen var feil, og
        testen avdekket det ved å feile. Den er omskrevet — ikke slakket — til å
        låse det som faktisk er sant. Finans verifiserte uavhengig og godkjente.

        Målt på Dev `35275074` etter FULL betaling via veiviseren:
            payment_state  = in_payment    (IKKE «paid»)
            amount_residual = 3000.0        (IKKE 0 — restbeløpet står urørt)
        Målt på fiqas Production (`https://www.fiq.no`):
            0 av 20 kundefakturaer er `paid` · alle 27 betalinger er `in_process`

        `paid` kommer FØRST ved BANKAVSTEMMING. Derfor teller en registrert-men-
        uavstemt betaling fortsatt som utestående i `_basis_domene`.

        🛑 DET ER DET KONSERVATIVE VALGET, OG DET ER BEVISST: penger som ikke er
        bankbekreftet er ikke penger på konto. Å telle dem som mottatt er den
        farligere feilen — daglig leder får en likviditetskurve som viser dekning
        som ikke finnes.

        🛑 IKKE «FIKS» DETTE MED `amount_residual != 0`: Finans målte at
        restbeløpet er 3000 etter full betaling. Filteret ville ikke virket —
        bare gjort domenet mer komplisert uten effekt.

        📌 Om uavstemte betalinger SKAL telle som utestående er et regnskaps-
        spørsmål, ikke et kodespørsmål. Det ligger hos Gjermund (oppgave 08.07).
        Uansett svar er dagens forsiktige valg + synlig forklaring riktig.
        """
        faktura = self._faktura(-5, belop=3000.0)
        for_ = self.Data.hent_grunnbilde()["botter"][4]["verdi"]

        # Registrer full betaling via Odoos egen wizard — aldri rå ORM på regnskap.
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=faktura.ids,
        ).create({})
        wizard.action_create_payments()

        # 🔴 MILJØAVHENGIG (målt 23.07 på to baser): utfallet av veiviseren
        # avhenger av bankjournalens utestående-konto, ikke av vår kode.
        #   fiqas Production:  in_payment · residual urørt
        #   Dev 35326209:      paid       · residual 0
        # Regelen vi låser er derfor SAMMENHENGEN, ikke den ene verdien:
        # er bilaget ikke bekreftet betalt, skal det bli stående i utestående.
        etter = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        if faktura.payment_state == "in_payment":
            self.assertNotEqual(faktura.amount_residual, 0.0,
                                "Restbeløpet står urørt til betalingen er avstemt")
            self.assertGreaterEqual(etter, for_,
                                    "Uavstemt betaling skal fortsatt telle som utestående")
        else:
            self.assertEqual(faktura.payment_state, "paid",
                             "Enten in_payment (uavstemt) eller paid (avstemt)")
            self.assertEqual(faktura.amount_residual, 0.0,
                             "Bekreftet betaling nullstiller restbeløpet")
        # Men flaten MÅ forklare hvorfor tallet ser høyt ut — ellers leses det
        # som manglende innbetaling. Det er halve forklaringen på likviditets-
        # bildet i Production, der 19 av 20 bilag ligger slik.
        # Merknaden gjelder bilag som VENTER på bekreftelse. Avstemmer basen
        # automatisk (som Dev-demodata gjør), finnes det ingen slike — og da
        # skal tallet være 0, ikke oppdiktet. Feltet må uansett finnes.
        d = self.Data.hent_grunnbilde()
        self.assertIn("i_betaling_antall", d)
        if faktura.payment_state == "in_payment":
            self.assertGreater(d["i_betaling_antall"], 0,
                               "Grunnbildet må si fra om registrerte, uavstemte betalinger")

    # ---------- SAMLEBOKS (KR-kontrakt) ----------

    def test_kr_boks_har_kontraktens_felter(self):
        """KR-kontrakten (fiq_gui_control_config.py:1335) krever fire nøkler.

        Mangler én, får KR en KeyError og forsiden mister boksen — eller verre,
        alle boksene hvis KR ikke fanger unntaket per flate.
        """
        b = self.Data.get_kr_boks()
        for felt in ("haster", "i_dag", "totalt", "linjer"):
            self.assertIn(felt, b, "get_kr_boks mangler kontraktsfeltet %r" % felt)
        self.assertIsInstance(b["totalt"], int)
        self.assertIsInstance(b["linjer"], list)

    def test_kr_boks_linjer_har_tekst_og_res_id(self):
        """Hver linje må ha tekst + res_id — ellers kan KR ikke lage klikkbar rad."""
        self._faktura(-45, belop=8000.0)
        for linje in self.Data.get_kr_boks()["linjer"]:
            self.assertIn("tekst", linje)
            self.assertIn("res_id", linje)
            self.assertTrue(linje["tekst"], "Tom tekst gir en blank rad i KR")

    def test_kr_boks_taaler_tom_base(self):
        """🔴 Dev bygger fra TOM base med demodata — helt andre bilag enn Staging.

        Metoden må svare uten å krasje selv om det ikke finnes ÉN ubetalt faktura.
        Dette er nøyaktig feilklassen Dev-leddet skal fange (AI PK 22.07).
        """
        tom = self.Data.with_context(active_test=False)
        b = tom.get_kr_boks()
        self.assertIsInstance(b["totalt"], int)
        self.assertGreaterEqual(b["totalt"], 0)

    # ---------- CASHFLOW-FRAMSKRIVNING ----------

    def test_cashflow_har_ukepunkter_og_aerlig_mangelliste(self):
        """Kurven må ALLTID oppgi hva den ikke tar høyde for.

        🛑 `mangler` er ikke pynt: uten lønn/avgift/feriepenger/pensjon er kurven
        ufullstendig, og en ufullstendig likviditetskurve som ser komplett ut er
        farligere enn ingen kurve. Fjernes listen, skal denne testen stoppe det.
        """
        c = self.Data.hent_cashflow(uker=12)
        self.assertEqual(len(c["punkter"]), 12)
        # `mangler` ble strukturert i 1.22.0 (navn → navn + grunn + forklaring),
        # så typene sjekkes på `navn`-feltet i stedet for på rå strenger.
        navn = [m["navn"] for m in c["mangler"]]
        self.assertIn("Lønnskjøringer", navn)
        self.assertIn("Feriepenger", navn)
        self.assertTrue(c["grunnlag"], "Kurven må oppgi hva den bygger på")

    def test_cashflow_saldo_akkumulerer(self):
        """Saldoen skal bygge på forrige uke — ikke vise ukens netto isolert.

        En kurve der hver uke starter på null svarer ikke på «når blir det tight».
        """
        self._faktura(3, belop=10000.0)    # inn uke 1
        self._faktura(10, belop=5000.0)    # inn uke 2
        c = self.Data.hent_cashflow(uker=4)
        self.assertGreaterEqual(
            c["punkter"][1]["saldo"], c["punkter"][0]["saldo"],
            "Saldo skal akkumulere: uke 2 må inkludere uke 1",
        )

    def test_cashflow_finner_laveste_punkt(self):
        """«Når blir det tight» = laveste punkt i kurven, ikke siste."""
        self._faktura(5, belop=2000.0, type_="in_invoice")   # ut → drar saldo ned
        c = self.Data.hent_cashflow(uker=8)
        saldoer = [p["saldo"] for p in c["punkter"]]
        self.assertEqual(c["laveste"]["saldo"], min(saldoer + [c["start_saldo"]]))
        self.assertTrue(c["laveste"]["dato"])

    def test_cashflow_taaler_tom_base(self):
        """Uten ett eneste ubetalt bilag skal kurven svare, ikke krasje."""
        c = self.Data.hent_cashflow(uker=4)
        self.assertEqual(len(c["punkter"]), 4)
        self.assertIsInstance(c["start_saldo"], float)

    def test_cashflow_kun_eget_firma(self):
        """🛑 Framskrivning bygger på samme domene — tenant-grensen må holde."""
        self._faktura(7, belop=4000.0)
        c = self.Data.hent_cashflow(uker=4)
        # Summen kan aldri overstige firmaets eget utestående.
        eget = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        total_i_kurven = sum(abs(p["inn"]) + abs(p["ut"]) for p in c["punkter"])
        self.assertLessEqual(round(total_i_kurven, 2), round(abs(eget), 2) + 0.01)

    # ---------- KLIKK: TALL → LISTE ----------

    def test_apne_botte_gir_gyldig_handling(self):
        """«Tall → klikk → liste», aldri blindvei (GUI Prosjekt 19.07).

        view_mode må være «list» — «tree» er Odoo 18-syntaks og ugyldig i 19.
        """
        for key in ("inn", "ut", "haster", "kritisk", "ubetalt"):
            handling = self.Data.apne_botte(key)
            self.assertEqual(handling["res_model"], "account.move")
            self.assertIn("list", handling["view_mode"])
            self.assertNotIn("tree", handling["view_mode"], "«tree» er Odoo 18-syntaks")
            # Domenet må være kjørbart — ikke bare velformet.
            self.Move.search_count(handling["domain"])

    # ---------- TENANT-ISOLASJON ----------

    def test_kun_eget_firma(self):
        """🛑 HARD GRENSE: en annen tenants tall skal ALDRI kunne lekke inn.

        Alle domener må binde company_id til sesjonens firma. Lekker dette,
        ser ett firma et annet firmas regnskap — brudd på membranen.
        """
        for key in ("inn", "ut", "haster", "kritisk", "ubetalt"):
            domene = self.Data.apne_botte(key)["domain"]
            firma_ledd = [d for d in domene if isinstance(d, (list, tuple))
                          and d[0] == "company_id"]
            self.assertTrue(firma_ledd, "%s mangler company_id — tenant-lekkasje" % key)
            self.assertEqual(firma_ledd[0][2], self.env.company.id)

    def test_scope_merket_teller_tilgang_ikke_aktiverte(self):
        """🔴 REGRESJON (min egen feil, v1.13.0 → v1.14.0).

        Jeg brukte env.companies (firmaer AKTIVERT i sesjonen) der jeg mente
        env.user.company_ids (firmaer brukeren HAR TILGANG TIL). Følgen: merket
        «Kun X — du har tilgang til N firmaer» forsvant nettopp når brukeren hadde
        skrudd AV de andre firmaene — altså når tallet var MEST ufullstendig.
        """
        d = self.Data.hent_grunnbilde()
        self.assertEqual(d["antall_firmaer"], len(self.env.user.company_ids))

    # ---------- TIDLIG KORRIGERING (08.03.01) ----------

    def _betal(self, faktura, dager_etter_forfall):
        """Registrerer en innbetaling på en faktura, med kjent dato.

        🔴 LÆRDOM (min egen feil, v1.19.0): første forsøk opprettet betalingen med
        rå ORM og reconcile(). Det felte ikke bare mine egne tester — det felte
        `test_betalt_faktura_teller_ikke`, en test som virket før jeg rørte noe.
        Rå ORM setter ikke opp mot-postene Odoo forventer, så koblingen
        betaling→faktura (`reconciled_invoice_ids`) ble aldri opprettet.

        Riktig vei er den `test_betalt_faktura_teller_ikke` allerede brukte:
        Odoos egen betalingsveiviser. Husets regel «aldri rå ORM på regnskap»
        gjelder også i tester — testen skal speile hvordan systemet faktisk brukes.

        Speiler fiqas Production: betalingen blir REGISTRERT, men ikke avstemt
        mot bank (`is_matched = False`). Motoren må finne den likevel.
        """
        betalingsdato = fields.Date.add(faktura.invoice_date_due, days=dager_etter_forfall)
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=faktura.ids,
        ).create({"payment_date": betalingsdato})
        wizard.action_create_payments()
        return self.env["account.payment"].search(
            [("partner_id", "=", faktura.partner_id.id)], order="id desc", limit=1
        )

    def test_betalingsmonster_maaler_dager_etter_forfall(self):
        """Kjernen i tidlig korrigering: HVOR sent betaler kunden faktisk?

        Uten dette tallet er «kortere frister» en gjetning. 30 dager forsinkelse
        skal måles som 30 — ikke som «betalt» eller «ikke betalt».
        """
        faktura = self._faktura(-60, belop=10000.0)
        self._betal(faktura, 30)

        m = self.Data.hent_betalingsmonster()
        # `display_name`, ikke `name`: på fiqas har partnere kundenummer foran
        # («10088 FIQ Testkunde AS»). Salgssporet meldte samme felle 22.07 —
        # navnet er BEREGNET, og en test som sammenligner med råfeltet feiler
        # på en base med nummerering, men er grønn på en uten.
        mine = [x for x in m["motparter"] if x["motpart"] == self.kunde.display_name]
        self.assertTrue(mine, "Motparten mangler i mønsteret")
        self.assertAlmostEqual(mine[0]["snitt_dager"], 30.0, places=1)
        self.assertTrue(mine[0]["betaler_sent"])

    def test_betalingsstatus_brukes_ikke_som_maal(self):
        """🔴 KRITISK: motoren må IKKE bygge på `payment_state`.

        Målt på fiqas Production 22.07: 0 av 20 fakturaer står som `paid` mens 27
        betalinger finnes. Et mål bygd på bilagets betalingsstatus ville rapportert
        «ingen data» der det finnes rikelig. Denne testen feiler hvis noen senere
        bytter til payment_state — da blir antallet 0.
        """
        faktura = self._faktura(-40, belop=5000.0)
        self._betal(faktura, 10)

        m = self.Data.hent_betalingsmonster()
        self.assertGreater(m["antall_fakturaer"], 0,
                           "Motoren fant ingen betalinger — bygger den på payment_state?")

    def test_tynt_grunnlag_gir_ikke_anbefaling(self):
        """🛑 «ALDRI gjett»: ett tilfelle er en anekdote, ikke et mønster.

        Én kunde med én faktura skal ALDRI gi grønt lys for en anbefaling.
        Vakten er bevisst — fjernes `godt_nok`, kan flaten anbefale kortere
        betalingsfrister på grunnlag av én enkelt hendelse.
        """
        faktura = self._faktura(-30, belop=1000.0)
        self._betal(faktura, 5)

        m = self.Data.hent_betalingsmonster()
        self.assertFalse(m["godt_nok"],
                         "Én motpart skal ikke være godt nok grunnlag for en anbefaling")

    def test_ubekreftede_betalinger_telles_men_merkes(self):
        """Registrert ≠ bekreftet. Begge deler må være synlig.

        En betaling som ikke er avstemt mot bank er ikke verifisert av banken.
        Å utelate den skjuler data; å telle den stille overdriver sikkerheten.
        Derfor: tell den, og si fra.
        """
        faktura = self._faktura(-20, belop=3000.0)
        self._betal(faktura, 7)

        m = self.Data.hent_betalingsmonster()
        self.assertGreater(m["ubekreftede_betalinger"], 0,
                           "Uavstemt betaling skal telles som ubekreftet")
        self.assertTrue(m["forbehold"], "Forbeholdet må stå i datasettet, ikke bare i visningen")

    def test_grunnbildet_sier_fra_om_uavstemte_bilag(self):
        """🔴 «Registrert betalt» er ikke «bekreftet betalt» — og det må SYNES.

        Målt på fiqas Production 22.07 (www.fiq.no): 19 av 20 kundefakturaer står
        som `in_payment` og alle 27 betalinger som `in_process`. Odoo setter ikke
        `paid` før betalingen er avstemt mot bankutskrift, og `amount_residual`
        står urørt. `_basis_domene` teller dem derfor som UTESTÅENDE.

        Det er et bevisst konservativt valg — men et tall som er konservativt uten
        å si det, leses som eksakt. Denne testen låser at grunnbildet forteller
        hvor mange bilag som ligger i den tilstanden.

        📌 Samme mekanisme er årsaken til at `test_betalt_faktura_teller_ikke`
        feiler på en base uten bankavstemming: fakturaen ER betalt, men får
        `in_payment`, ikke `paid`. Den testen er IKKE feil — den avdekker
        begrensningen. Om `_basis_domene` skal endres er en menneskelig
        avgjørelse (Finans 2.70 + Gjermund), ikke et kodevalg her.
        """
        faktura = self._faktura(-15, belop=4000.0)
        self._betal(faktura, 5)

        d = self.Data.hent_grunnbilde()
        # 🔴 MÅLT 23.07 — `in_payment` vs `paid` er MILJØAVHENGIG, ikke universelt:
        #   fiqas Production (www.fiq.no):      in_payment · residual urørt
        #   Dev 35326209 (ny demodata-base):    paid       · residual 0
        # Forskjellen ligger i bankjournalens oppsett (utestående-konto), ikke i
        # vår kode. En test som krever «in_payment» låser derfor et MILJØ, ikke en
        # regel — og feiler når basen bygges på nytt. Min forrige versjon gjorde
        # nettopp det. Vi tester i stedet det som ALLTID er sant: er bilaget
        # fortsatt utestående, MÅ flaten forklare hvorfor.
        if faktura.payment_state == "in_payment":
            self.assertGreater(d["i_betaling_antall"], 0,
                               "Grunnbildet må si fra om bilag som er registrert betalt")
            self.assertTrue(d["i_betaling_merknad"],
                            "Merknaden må stå i datasettet, ikke bare i visningen")
        else:
            # Basen avstemmer automatisk → bilaget er ute av bildet. Da skal det
            # heller ikke meldes som ventende. Feltene må uansett finnes.
            self.assertIn("i_betaling_antall", d)
            self.assertIn("i_betaling_merknad", d)

    def test_uavstemt_betaling_finnes_i_monsteret(self):
        """🔴 REGRESJON (min egen feil, v1.19.0 → v1.19.2).

        Jeg koblet betaling→faktura via `reconciled_invoice_ids`. Den fylles
        FØRST NÅR betalingen er avstemt mot bank. Målt på Dev 22.07:
            reconciled_invoice_ids: []      ← tom
            invoice_ids: ['INV/2026/00010']  ← koblingen finnes her
        På fiqas Production står ALLE 27 betalinger som `in_process` (uavstemt).
        Motoren ville rapportert «ingen betalinger» på en base med 27 av dem —
        og det er nøyaktig den basen flaten skal brukes på.

        Denne testen feiler hvis noen bytter tilbake til reconciled_invoice_ids.
        """
        faktura = self._faktura(-45, belop=8000.0)
        betaling = self._betal(faktura, 15)

        self.assertFalse(betaling.is_matched,
                         "Forutsetningen for testen: betalingen skal være uavstemt")
        m = self.Data.hent_betalingsmonster()
        self.assertGreater(m["antall_fakturaer"], 0,
                           "Uavstemt betaling må finnes i mønsteret — bruker koden "
                           "reconciled_invoice_ids i stedet for invoice_ids?")

    def test_malen_leser_manglerlista_slik_modellen_gir_den(self):
        """🔴 REGRESJON — Gjermund så «[object Object]» fire ganger i flaten 23.07.

        Årsak: i 1.22.0 gikk `mangler` fra en liste med NAVN til en liste med
        OBJEKTER (navn + grunn + forklaring). Modellen ble oppdatert; malen ble
        stående på `mangler.join(' · ')`. Å `join`-e objekter gir «[object Object]».

        🔑 DET EGENTLIGE HULLET: 30 tester dekket modellen, null dekket VISNINGEN.
        Alle var grønne mens flaten skrev søppel til daglig leder. Samme familie
        som dagens andre funn — «riktig form, feil innhold», bare ett lag opp.

        Denne testen leser malen som tekst og krever at den ikke `join`-er lista,
        men plukker feltene ut. Den kan ikke rendre QWeb, men den fanger nettopp
        den utaktsfeilen som oppsto her.
        """
        import os
        sti = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                           "static", "src", "rgs.xml")
        with open(sti, encoding="utf-8") as f:
            mal = f.read()

        self.assertNotIn("mangler.join", mal,
                         "Malen join-er mangler-lista — det gir «[object Object]» "
                         "siden lista inneholder objekter, ikke tekst")
        # Feltene modellen faktisk leverer må brukes, ellers vises ingenting.
        self.assertIn("m.navn", mal, "Malen må vise navnet på hver manglende type")
        self.assertIn("m.forklaring", mal,
                      "Malen må vise forklaringen — hele poenget med å strukturere lista")

        # Og feltene må finnes i det modellen gir, ikke bare i malen.
        for m in self.Data.hent_cashflow()["mangler"]:
            self.assertIn("navn", m)
            self.assertIn("forklaring", m)

    def test_mangler_sier_hvorfor_ikke_bare_hva(self):
        """🔴 TRE TILSTANDER, IKKE TO (funnet 23.07 sammen med 2.20 Lønn).

        Den gamle `mangler` var en flat liste med navn. Da kunne en type som var
        KOBLET, men uten data for selskapet, blitt fjernet — og kurven sett
        komplett ut mens en hel forpliktelsestype manglet. Nøyaktig det lista
        finnes for å hindre.

        Konkret tilfelle fra Lønn: et selskap uten registrert sone for
        arbeidsgiveravgift gir INGEN AGA-linjer — ikke null kroner. «Levert, men
        tomt» må derfor kunne skilles fra «ikke bygd ennå».
        """
        c = self.Data.hent_cashflow()
        self.assertTrue(c["mangler"], "Lista skal ikke være tom før alt er koblet")
        for m in c["mangler"]:
            for felt in ("type", "navn", "grunn", "forklaring"):
                self.assertIn(felt, m, "mangler-linja mangler feltet %r" % felt)
            self.assertTrue(m["forklaring"],
                            "En manglende type må forklares, ikke bare navngis")

    def test_grunnen_hentes_fra_lonn_naar_modulen_finnes(self):
        """🔴 REGRESJON (min egen feil, 1.22.3 → 1.22.4) — koblingen var DØD.

        Alle 26 tester var grønne mens flaten meldte «ikke bygd» for alle fire
        typene, samtidig som 2.20 Lønn svarte `mangler_sone` på AGA. Ingen test
        sammenlignet de to sidene, så feilen var usynlig.

        Årsak: `finnes and env[modell] or None` faller ALLTID til None — et tomt
        recordset er falskt i Python. Oppslaget slo derfor aldri til.

        Denne testen sammenligner flatens `grunn` med Lønns egen status. Er de
        ulike, er koblingen brutt — uansett hva de andre testene sier.
        """
        if not self.env["ir.model"].sudo().search_count(
                [("model", "=", "fiq.lonnsforpliktelse")]):
            self.skipTest("Lønnsmodulen er ikke installert på denne basen")

        i_dag = fields.Date.context_today(self.Data)
        status = self.env["fiq.lonnsforpliktelse"].status_forpliktelser(
            i_dag, fields.Date.add(i_dag, days=84))
        mine = {m["type"]: m["grunn"] for m in self.Data.hent_cashflow()["mangler"]}

        for kode, info in status.items():
            if info.get("levert"):
                self.assertNotIn(kode, mine,
                                 "%s er levert av Lønn og skal være ute av lista" % kode)
                continue
            self.assertEqual(
                mine.get(kode), info.get("grunn"),
                "Flaten melder «%s» for %s, men Lønn sier «%s» — koblingen er brutt"
                % (mine.get(kode), kode, info.get("grunn")))

    def _falsk_lonn(self, dager_frem, belop=50000.0, sikkerhet="planlagt"):
        """Setter inn en kjent lønnsforpliktelse i kurven, uten lønnsmodulen.

        🔴 HVORFOR DENNE FINNES (2.20 Lønn, 23.07): deres kontrakttester
        itererte over en TOM liste — løkka kjørte aldri, testen passerte alltid.
        Mine tre første kurve-tester hadde nøyaktig samme feil: målt på Dev ga
        `lonn_linjer` 0 elementer, så alle tre var grønne uten å teste noe.

        Vi kan ikke opprette ekte lønnsslipper her — det er 2.20 Lønns domene,
        og en test som krever deres modul ville brutt det myke oppslaget. Vi
        overstyrer derfor henteren med kjente linjer, og tester VÅR plassering
        og merking av dem. Deres side testes hos dem (test 25 hos Lønn).
        """
        i_dag = fields.Date.context_today(self.Data)
        linjer = [{
            "type": "aga", "label": "Arbeidsgiveravgift",
            "forfall": fields.Date.add(i_dag, days=dager_frem),
            "belop": belop, "sikkerhet": sikkerhet, "kilde": "Odoo",
            "periode": "Termin 1 2026", "merknad": "",
        }]
        Data = type(self.Data)
        original = Data._hent_lonnslinjer

        def falsk(self_, fra, til):
            return [l for l in linjer if fra <= l["forfall"] < til]

        Data._hent_lonnslinjer = api.model(falsk)
        self.addCleanup(setattr, Data, "_hent_lonnslinjer", original)
        return linjer[0]

    def test_lonnslinjer_plasseres_etter_forfall_ikke_periode(self):
        """🔑 Lønn plasseres etter FORFALL — `periode` er ren visning.

        Avtalt med 2.20 Lønn 22.07: augustlønn betalt 15. september hører i
        septemberuka, uansett hva perioden heter. Forveksles de, forskyves
        hele likviditetsbildet — og det er nettopp derfor `periode` aldri får
        røre en beregning.

        Testen bruker kurvens egne uker, så den er sann uansett dagens dato.
        """
        self._falsk_lonn(dager_frem=17)  # midt i uke 2
        c = self.Data.hent_cashflow(uker=12)

        # 🔴 VAKTPOST: uten denne itererer testen over en tom liste og passerer
        # alltid — feilen 2.20 Lønn fant i sine egne kontrakttester 23.07.
        antall = sum(len(p["lonn_linjer"]) for p in c["punkter"])
        self.assertEqual(antall, 1, "Testen må ha data å måle på, ellers beviser den ingenting")

        for p in c["punkter"]:
            for linje in p["lonn_linjer"]:
                fra = fields.Date.to_date(p["fra"])
                til = fields.Date.add(fra, days=7)
                self.assertTrue(
                    fra <= linje["forfall"] < til,
                    "Lønnslinje med forfall %s havnet i uka som starter %s"
                    % (linje["forfall"], p["fra"]))

    def test_planlagt_lonn_ser_aldri_ut_som_bokfort(self):
        """🛑 «ALDRI gjett — regnskap er juridisk bindende.»

        2.20 Lønn merker hver linje `bokfort` · `planlagt` · `estimat`. En
        validert lønnskjøring som ikke er utbetalt er `planlagt` — en fremtidig
        utbetaling, ikke et bokført tall. Feltet må følge helt ut i flaten;
        mistes det, ser en framskrivning ut som fakta.

        Mangler `sikkerhet` på en linje, settes den til `estimat` — det
        forsiktige valget. Aldri `bokfort` for sikkerhets skyld.
        """
        self._falsk_lonn(dager_frem=10, sikkerhet="planlagt")
        gyldige = {"bokfort", "planlagt", "estimat"}
        funnet = []
        for p in self.Data.hent_cashflow()["punkter"]:
            for linje in p["lonn_linjer"]:
                self.assertIn(linje["sikkerhet"], gyldige,
                              "Ukjent sikkerhetsnivå %r" % linje["sikkerhet"])
                funnet.append(linje["sikkerhet"])

        # Vaktpost mot tom-liste-fella, og bevis på at nivået faktisk bæres helt
        # ut i kurven — ikke bare at det er gyldig når det finnes.
        self.assertEqual(funnet, ["planlagt"],
                         "«planlagt» må følge uendret ut i flaten, ikke bli bokført")

    def test_lonn_teller_med_i_ut_og_saldo(self):
        """Lønn er penger UT — den må påvirke saldoen, ikke bare vises.

        `lonn_ut` finnes for at flaten skal kunne forklare et brått hopp (f.eks.
        når AGA-fribeløpet er brukt opp). Men den skal være en DEL av `ut`, ikke
        et sidespor — ellers viser kurven en likviditet firmaet ikke har.
        """
        self._falsk_lonn(dager_frem=10, belop=50000.0)
        punkter = self.Data.hent_cashflow()["punkter"]

        # Vaktpost: uten lønn i kurven ville løkka under ikke bevist noe.
        self.assertGreater(sum(p["lonn_ut"] for p in punkter), 0,
                           "Testen må ha et lønnsbeløp å måle på")

        for p in punkter:
            self.assertGreaterEqual(
                p["ut"], p["lonn_ut"],
                "Lønnsbeløpet må være inkludert i ukas «ut», ikke stå utenfor")

        # Og saldoen må faktisk trekkes ned — ellers vises likviditet firmaet
        # ikke har. `lonn_ut` skal være en del av regnestykket, ikke pynt.
        uke = next(p for p in punkter if p["lonn_ut"] > 0)
        self.assertGreaterEqual(uke["ut"], 50000.0,
                                "Lønnsutbetalingen må slå ut i ukas «ut»")

    def test_flaten_virker_uten_lonnsmodulen(self):
        """🛑 `fiq_rgs_lonn` er IKKE en avhengighet — og skal aldri bli det.

        En base uten lønn er en normal base, ikke en feil. Ville flaten krasjet
        eller returnert tom `mangler` når modulen ikke finnes, hadde vi enten
        felt regnskapsflaten på alle slike baser, eller — verre — vist en kurve
        som ser komplett ut fordi ingenting ble meldt som manglende.

        Testen kjører på en base der `fiq_rgs_lonn` ikke er installert, og er
        derfor beviset i seg selv: kommer vi hit med fire forklarte linjer,
        virker det myke oppslaget.
        """
        # 🔴 MÅLT 23.07: `env.get('ukjent.modell')` gir et TOMT RECORDSET, ikke
        # None. En None-sjekk ville vært grønn av feil grunn. Riktig test på om
        # en modell finnes er modellregisteret.
        #
        # 🔴 OG: min forrige versjon KREVDE at modulen ikke var installert. Det
        # var å låse et miljø, ikke en regel — Dev `35326209` har den installert,
        # Production har den ikke. Testen må gjelde BEGGE veier, ellers feiler
        # den på annenhver base.
        finnes = bool(self.env["ir.model"].sudo().search_count(
            [("model", "=", "fiq.lonnsforpliktelse")]))
        c = self.Data.hent_cashflow()

        self.assertIsInstance(c["mangler"], list,
                              "Flaten må svare uansett om lønnsmodulen finnes")
        for m in c["mangler"]:
            self.assertTrue(m["forklaring"], "Hver manglende type må forklares")

        if not finnes:
            # Uten modulen: alle fire meldes som ikke bygd — aldri en tom liste,
            # for en tom `mangler` leses som «alt er med i kurven».
            self.assertEqual(len(c["mangler"]), 4,
                             "Uten lønnsmodulen skal alle fire meldes som manglende")
            self.assertTrue(all(m["grunn"] == "ikke_bygd" for m in c["mangler"]))

    def test_bilag_forsvinner_forst_naar_bekreftet_mot_bank(self):
        """🛑 GJERMUNDS AVGJØRELSE 23.07 (08.10) — låst i test.

            «De skal være registrert betalt før de forsvinner — ikke nødvendigvis
             månedlig bankavstemming, men ja: en avstemming mot bank.»

        Et bilag forlater likviditetsbildet FØRST når betalingen er bekreftet mot
        bank. `payment_state = in_payment` = registrert, ikke bekreftet — og skal
        derfor fortsatt telle som utestående.

        Denne testen feiler hvis noen senere «rydder» `_basis_domene` til å slippe
        gjennom `in_payment`. Det ville vist penger som kanskje aldri kom inn.
        """
        faktura = self._faktura(-10, belop=6000.0)
        for_ = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self._betal(faktura, 3)

        etter = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        # Miljøavhengig (målt 23.07): Production gir `in_payment`, en fersk
        # demodata-base gir `paid` fordi bankjournalen er satt opp ulikt.
        # Regelen vi låser er Gjermunds: er betalingen IKKE bekreftet, skal
        # bilaget bli stående. Er den bekreftet, skal det ut.
        if faktura.payment_state == "in_payment":
            self.assertGreaterEqual(
                etter, for_,
                "Registrert-men-ubekreftet betaling skal IKKE fjerne bilaget "
                "fra utestående (Gjermund 08.10)")
        else:
            self.assertLessEqual(
                etter, for_,
                "Bekreftet betaling skal ta bilaget UT av utestående")

    def test_flaten_sier_om_bankavstemming_er_mulig(self):
        """Tallet må kunne forklare seg selv — ellers leses det som slurv.

        «19 bilag venter på bekreftelse» betyr noe helt ulikt avhengig av om
        bankkoblingen finnes og ikke brukes, eller ikke finnes i det hele tatt.
        Målt på fiqas Production 23.07: bankjournalen har verken kontonummer
        eller kilde, og det finnes 0 kontoutskriftslinjer.
        """
        b = self.Data.hent_grunnbilde()["bankavstemming"]
        for felt in ("bankjournaler", "uten_kilde", "utskriftslinjer",
                     "avstemming_mulig", "merknad"):
            self.assertIn(felt, b, "bankavstemming mangler feltet %r" % felt)
        # Er avstemming umulig, MÅ merknaden forklare hvorfor — ellers står
        # brukeren igjen med et tall uten årsak.
        if not b["avstemming_mulig"]:
            self.assertTrue(b["merknad"],
                            "Umulig avstemming må forklares, ikke bare flagges")

    def test_base_merket_oppgir_server_ikke_bare_firma(self):
        """🔑 LÆRDOM 22.07: firmanavn identifiserer INNHOLD, ikke SERVER.

        «FIQ as» finnes på både Staging og Production. Fire økter rapporterte tall
        fra feil base samme dag fordi ingen målte `web.base.url`. Uten dette merket
        kan et demodata-tall leses som ekte i en rapport bygget oppå flaten.
        """
        m = self.Data.hent_betalingsmonster()
        self.assertIn("url", m["base"], "Base-merket må oppgi server-URL, ikke bare firma")
        self.assertIn("firma", m["base"])

