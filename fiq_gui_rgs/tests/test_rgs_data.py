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

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_rgs")
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

    def test_betalt_faktura_teller_ikke(self):
        """Ekte mønster fra Staging: alle 4 leverandørfakturaer hadde restbeløp 0.

        «Utgående = 0» så ut som en kodefeil, men var korrekt. Denne testen låser
        oppførselen: betalte bilag skal ut av likviditetsbildet.
        """
        faktura = self._faktura(-5, belop=3000.0)
        for_ = self.Data.hent_grunnbilde()["botter"][4]["verdi"]

        # Registrer full betaling via Odoos egen wizard — aldri rå ORM på regnskap.
        wizard = self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=faktura.ids,
        ).create({})
        wizard.action_create_payments()

        etter = self.Data.hent_grunnbilde()["botter"][4]["verdi"]
        self.assertLess(etter, for_, "Betalt faktura skal ut av ubetalt-summen")

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
        self.assertIn("Lønnskjøringer", c["mangler"])
        self.assertIn("Feriepenger", c["mangler"])
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
        mine = [x for x in m["motparter"] if x["motpart"] == self.kunde.name]
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

    def test_base_merket_oppgir_server_ikke_bare_firma(self):
        """🔑 LÆRDOM 22.07: firmanavn identifiserer INNHOLD, ikke SERVER.

        «FIQ as» finnes på både Staging og Production. Fire økter rapporterte tall
        fra feil base samme dag fordi ingen målte `web.base.url`. Uten dette merket
        kan et demodata-tall leses som ekte i en rapport bygget oppå flaten.
        """
        m = self.Data.hent_betalingsmonster()
        self.assertIn("url", m["base"], "Base-merket må oppgi server-URL, ikke bare firma")
        self.assertIn("firma", m["base"])

