"""Tester for Finansflatens datalag (fiq.gui.fin.data) — kredittrisiko per kunde.

2.70 svarer på et ANNET spørsmål enn 2.80: ikke «hva forfaller», men «hvilke KUNDER
skylder mye og lenge». Gjermunds spec: «kunder med faresignaler som skylder mye penger».

PORT 6: hver test oppretter sin egen tilstand. Terskelen (10 000 kr / 30 dager) må
testes fra begge sider — ellers vet vi ikke om den virker eller bare ser riktig ut.
"""

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "fiq_fin")
class TestFinData(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Data = cls.env["fiq.gui.fin.data"]
        cls.Move = cls.env["account.move"]
        cls.i_dag = fields.Date.context_today(cls.Data)
        cls.produkt = cls.env["product.product"].create(
            {
                "name": "FIQ Testtjeneste FIN",
                "type": "service",
            }
        )

    @classmethod
    def _kunde(cls, navn):
        return cls.env["res.partner"].create({"name": navn})

    @classmethod
    def _faktura(cls, kunde, dager_til_forfall, belop):
        faktura = cls.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": kunde.id,
                "invoice_date": cls.i_dag,
                "invoice_date_due": fields.Date.add(cls.i_dag, days=dager_til_forfall),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": cls.produkt.id,
                            "quantity": 1,
                            "price_unit": belop,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        faktura.action_post()
        return faktura

    def _faresignal_navn(self):
        return " ".join(linje["tekst"] for linje in self.Data.get_kr_boks()["linjer"])

    # ---------- TERSKELEN: BEGGE VILKÅR MÅ VÆRE OPPFYLT ----------

    def test_mye_og_lenge_gir_faresignal(self):
        """Skylder BÅDE mye (≥10k) OG lenge (≥30 dager) → faresignal."""
        kunde = self._kunde("FIQ Test Faresignal AS")
        self._faktura(kunde, -45, 25000.0)
        self.assertIn("FIQ Test Faresignal AS", self._faresignal_navn())

    def test_stort_men_ferskt_er_ikke_risiko(self):
        """🔴 Et stort FERSKT beløp er ikke kredittrisiko — det er bare en faktura.

        Uten dette skillet ville hver ny storkunde blitt flagget som problem.
        """
        kunde = self._kunde("FIQ Test Ferskt Stort AS")
        self._faktura(kunde, -2, 90000.0)  # stort, men bare 2 dager forfalt
        self.assertNotIn("FIQ Test Ferskt Stort AS", self._faresignal_navn())

    def test_gammel_bagatell_er_ikke_risiko(self):
        """Motsatt side: en gammel småsum er heller ikke risiko."""
        kunde = self._kunde("FIQ Test Gammel Bagatell AS")
        self._faktura(kunde, -400, 250.0)
        self.assertNotIn("FIQ Test Gammel Bagatell AS", self._faresignal_navn())

    # ---------- KR-KONTRAKTEN ----------

    def test_kr_boks_har_kontraktens_felter(self):
        b = self.Data.get_kr_boks()
        for felt in ("haster", "i_dag", "totalt", "linjer"):
            self.assertIn(felt, b, f"get_kr_boks mangler kontraktsfeltet {felt!r}")
        self.assertIsInstance(b["haster"], int)

    def test_kr_boks_taaler_tom_base(self):
        """Dev bygger fra tom base — metoden må svare uten ubetalte fakturaer."""
        b = self.Data.get_kr_boks()
        self.assertGreaterEqual(b["totalt"], 0)
        self.assertIsInstance(b["linjer"], list)

    def test_linjer_bruker_navn_ikke_id(self):
        """Husets regel: navn, ikke ID-numre. En linje med «res.partner(42,)» er ubrukelig."""
        kunde = self._kunde("FIQ Test Navnevisning AS")
        self._faktura(kunde, -60, 30000.0)
        tekster = self._faresignal_navn()
        self.assertIn("FIQ Test Navnevisning AS", tekster)
        self.assertNotIn("res.partner(", tekster)

    # ---------- KPI-VELGER (native-først) ----------

    def test_kpi_peker_paa_odoos_egne_rapporter(self):
        """🛑 NATIVE-FØRST: hver KPI må peke på en EKTE Odoo-rapport-handling.

        Bygger vi egne rapporter, får vi to sannheter om samme tall — og den ene
        blir feil først. Denne testen låser at vi kun peker, aldri gjenskaper.

        📌 KREVER IKKE at lista er ikke-tom. `account_reports` er Enterprise og
        står bevisst IKKE i `depends` — modulen skal kunne installeres uten den
        og bare vise færre KPI-er. På en base uten Enterprise er tom liste
        RIKTIG oppførsel, ikke en feil. (AI IQ 24.07: fem tester feilet i gaten
        fordi de forventet at rapportene alltid finnes.)
        """
        res = self.Data.hent_kpi_valg()
        for r in res["rapporter"]:
            self.assertTrue(
                r["xmlid"].startswith("account_reports."),
                "KPI må peke på Odoos egen rapport, ikke vår egen",
            )
            self.assertTrue(
                self.env.ref(r["xmlid"], raise_if_not_found=False),
                f"xmlid {r['xmlid']} finnes ikke i basen",
            )

    def test_kpi_hopper_over_manglende_rapporter(self):
        """En rapport som ikke er installert skal utelates, ikke krasje.

        Odoo Enterprise-moduler kan mangle hos en kunde. Et kort som peker på en
        handling som ikke finnes gir feilmelding i stedet for rapport.
        """
        res = self.Data.hent_kpi_valg()
        # Alle returnerte må la seg slå opp — det er hele poenget med filteret.
        for r in res["rapporter"]:
            self.assertIsNotNone(self.env.ref(r["xmlid"], raise_if_not_found=False))

    def test_kpi_valg_lagres_per_bruker_og_firma(self):
        """Brukerens valg skal overleve — og ikke lekke til andre firmaer.

        Måler LAGRINGEN (`_valgte_kpier`), ikke visningen: uten Enterprise er
        `hent_kpi_valg()["rapporter"]` tom, men valget skal likevel være lagret.
        """
        self.Data.sett_valgte_kpier(["balanse"])
        self.assertEqual(self.Data._valgte_kpier(), ["balanse"])

    def test_kpi_forkaster_ukjente_nokler(self):
        """🛑 En klient skal ikke kunne skrive vilkårlige verdier inn i konfigurasjonen.

        `sett_valgte_kpier` tar imot en liste fra nettleseren. Uten filtrering
        kunne hva som helst havnet i `ir.config_parameter`.
        """
        self.Data.sett_valgte_kpier(["balanse", "noe_tull", "../../etc/passwd"])
        self.assertEqual(
            self.Data._valgte_kpier(), ["balanse"], "Ukjente nøkler skal forkastes"
        )

    def test_kpi_tomt_valg_gir_standard(self):
        """Ny bruker skal se de tre viktigste, ikke en tom flate eller alle åtte."""
        self.Data.sett_valgte_kpier([])
        self.assertEqual(set(self.Data._valgte_kpier()), set(self.Data.STANDARD_VALG))

    def test_apne_kpi_gir_gyldig_handling(self):
        """«Tall → klikk → rapport», aldri blindvei.

        📌 Finnes ikke `account_reports` (Enterprise), gir `apne_kpi` False —
        samme som for en ukjent nøkkel. Det er riktig: uten rapporten er det
        ingenting å åpne, og flaten skal ikke tilby en blindvei.
        """
        handling = self.Data.apne_kpi("balanse")
        if handling:
            self.assertIn("type", handling)
        self.assertFalse(
            self.Data.apne_kpi("finnes_ikke"),
            "Ukjent nøkkel skal gi False, ikke en tilfeldig handling",
        )

    # ---------- GRENSER OG KANTER ----------

    def test_noyaktig_paa_terskelen_teller_med(self):
        """🔴 GRENSE: ≥10 000 og ≥30 dager — ikke «over».

        Fanger: at noen bytter >= til > ved en opprydding. En kunde som skylder
        nøyaktig 10 000 i nøyaktig 30 dager ville da forsvunnet fra faresignalet
        uten at noe annet endret seg. Grensetilfeller er der regler ryker først.
        """
        kunde = self._kunde("FIQ Test Eksakt Terskel AS")
        self._faktura(kunde, -self.Data.FARE_DAGER, self.Data.FARE_BELOP)
        self.assertIn("FIQ Test Eksakt Terskel AS", self._faresignal_navn())

    def test_ett_hakk_under_terskelen_teller_ikke(self):
        """Motstykket: én krone og én dag under skal IKKE gi faresignal.

        Fanger: at terskelen flyttes stille. Uten begge sider vet vi ikke om
        grensen ligger der vi tror — bare at den finnes et sted.
        """
        kunde = self._kunde("FIQ Test Under Terskel AS")
        self._faktura(kunde, -(self.Data.FARE_DAGER - 1), self.Data.FARE_BELOP - 1)
        self.assertNotIn("FIQ Test Under Terskel AS", self._faresignal_navn())

    def test_kreditnota_trekker_ned_kundens_utestaaende(self):
        """🔴 En kreditnota reduserer det kunden faktisk skylder.

        Fanger: at `out_refund` faller ut av domenet ved en opprydding. Da ville
        en kunde med 25 000 i faktura og 20 000 i kreditnota blitt flagget for
        25 000 — et faresignal på penger som er kreditert bort. Det er feil tall
        foran daglig leder, ikke en kosmetisk bug.
        """
        kunde = self._kunde("FIQ Test Kreditnota AS")
        self._faktura(kunde, -60, 25000.0)
        kreditnota = self.Move.create(
            {
                "move_type": "out_refund",
                "partner_id": kunde.id,
                "invoice_date": self.i_dag,
                "invoice_date_due": fields.Date.add(self.i_dag, days=-60),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.produkt.id,
                            "quantity": 1,
                            "price_unit": 20000.0,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        kreditnota.action_post()
        # 25 000 − 20 000 = 5 000 → under terskelen, ikke lenger faresignal.
        self.assertNotIn("FIQ Test Kreditnota AS", self._faresignal_navn())

    # ---------- KONTRAKT MOT KONTROLLROMMET ----------

    def test_boksen_viser_hoyeste_beloep_forst(self):
        """🔴 KR viser bare de 5 øverste linjene. Rekkefølgen ER innholdet.

        Fanger: at sorteringen faller ut eller snus. Da ville daglig leder sett
        de fem minste kravene i stedet for de fem største — boksen ville sett
        riktig ut og vært verdiløs. Stille feil, verste sorten.
        """
        for belop in (15000.0, 90000.0, 40000.0):
            self._faktura(self._kunde(f"FIQ Sorttest {int(belop)} AS"), -60, belop)
        linjer = self.Data.get_kr_boks()["linjer"]
        beloep = [
            int(t) for linje in linjer for t in linje["tekst"].split() if t.isdigit()
        ]
        self.assertEqual(
            beloep, sorted(beloep, reverse=True), "Største krav skal stå øverst"
        )

    def test_boksen_klipper_paa_fem_linjer(self):
        """KR klipper uansett på 5 — men vi skal ikke sende mer enn vi lover.

        Fanger: at `[:5]` fjernes. Med 40 kunder ville boksen sendt 40 linjer
        over nettverket ved hver forsidelasting, og KR ville kastet 35 av dem.
        """
        for i in range(7):
            self._faktura(self._kunde(f"FIQ Klipptest {i} AS"), -60, 20000.0 + i)
        self.assertLessEqual(len(self.Data.get_kr_boks()["linjer"]), 5)

    def test_haster_teller_kunder_ikke_fakturaer(self):
        """🔴 2.70 teller KUNDER, 2.80 teller BILAG. Blandes de, er tallene like.

        Fanger: at noen «forenkler» ved å telle fakturaer. Én kunde med tre
        forfalte fakturaer skal gi haster=1, ikke 3 — ellers svarer boksen på
        2.80s spørsmål, og de to flatene blir duplikater.
        """
        kunde = self._kunde("FIQ Test Tre Fakturaer AS")
        for _n in range(3):
            self._faktura(kunde, -60, 15000.0)
        self.assertEqual(
            self.Data.get_kr_boks()["haster"],
            1,
            "Tre fakturaer fra SAMME kunde er ÉN kunde med faresignal",
        )

    # ---------- FRAVÆR: flaten skal TIE når grunnlaget mangler ----------

    def test_ingen_faresignal_gir_tom_liste_ikke_plassholder(self):
        """🔴 FRAVÆR: uten kunder over terskelen skal `linjer` være TOM.

        Fanger: at noen legger inn en «Ingen faresignaler»-linje i datalaget for
        å fylle boksen. KR ville da vist én rad som ser ut som et funn. Tomhet
        skal komme fram som tomhet — visningen bestemmer hvordan den formuleres,
        ikke datalaget.
        """
        self._faktura(self._kunde("FIQ Test Bare Ferskt AS"), -1, 50000.0)
        boks = self.Data.get_kr_boks()
        self.assertEqual(boks["haster"], 0)
        self.assertEqual(boks["linjer"], [], "Tomt skal være tomt, ikke en plassholder")

    def test_kunde_uten_forfallsdato_faller_ikke_gjennom_som_faresignal(self):
        """🔴 En faktura uten forfallsdato har ingen alder — den kan ikke være «gammel».

        Fanger: at `eldste and` fjernes fra vilkåret. `None` ville da sammenlignet
        seg til True i noen Python-varianter, og en fersk faktura uten forfall
        ville dukket opp som kredittrisiko. Feil kunde ringt, uten feilmelding.
        """
        kunde = self._kunde("FIQ Test Uten Forfall AS")
        faktura = self.Move.create(
            {
                "move_type": "out_invoice",
                "partner_id": kunde.id,
                "invoice_date": self.i_dag,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.produkt.id,
                            "quantity": 1,
                            "price_unit": 99000.0,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        faktura.action_post()
        self.assertNotIn("FIQ Test Uten Forfall AS", self._faresignal_navn())

    # ---------- TENANT ----------

    def test_company_id_fra_kr_kan_ikke_hente_annet_firmas_tall(self):
        """🛑 HARD GRENSE: KR sender `company_id` som parameter til `get_kr_boks`.

        Fanger: at `with_company()` byttes til å sette `company_id` direkte i
        domenet. Da ville en klient kunnet be om et hvilket som helst firmas
        kredittdata ved å sende inn en annen id. `with_company()` beholder
        Odoos `ir.rule`-håndheving; et rått domene gjør det ikke.

        Testen: be om et firma brukeren IKKE har tilgang til, og verifiser at
        vi ikke får det firmaets tall.
        """
        annet = self.env["res.company"].create({"name": "FIQ Testfirma Uten Tilgang"})
        # Brukeren har ikke dette firmaet i company_ids.
        self.assertNotIn(annet.id, self.env.user.company_ids.ids)

        kunde = self._kunde("FIQ Test Annet Firma AS")
        faktura = self.Move.with_company(annet).create(
            {
                "move_type": "out_invoice",
                "partner_id": kunde.id,
                "invoice_date": self.i_dag,
                "invoice_date_due": fields.Date.add(self.i_dag, days=-90),
                "company_id": annet.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.produkt.id,
                            "quantity": 1,
                            "price_unit": 80000.0,
                            "tax_ids": [(6, 0, [])],
                        },
                    )
                ],
            }
        )
        faktura.action_post()

        # Kallet skal ikke lekke det andre firmaets kunde inn i boksen.
        tekster = " ".join(
            linje["tekst"] for linje in self.Data.get_kr_boks()["linjer"]
        )
        self.assertNotIn(
            "FIQ Test Annet Firma AS",
            tekster,
            "Et annet firmas kredittdata lakk inn i boksen",
        )

    def test_kpi_valg_er_bundet_til_bruker_og_firma(self):
        """🔴 Parameternøkkelen MÅ inneholde både bruker-id og firma-id.

        Fanger: at nøkkelen forenkles til én global verdi. Da ville alle brukere
        i alle firmaer delt samme KPI-valg — én brukers oppsett ville overskrevet
        alle andres, stille.
        """
        self.Data.sett_valgte_kpier(["balanse"])
        param = self.env["ir.config_parameter"].sudo()
        forventet = f"fiq_gui_fin.kpi.{self.env.user.id}.{self.env.company.id}"
        self.assertEqual(
            param.get_param(forventet),
            "balanse",
            "KPI-valget skal ligge under en nøkkel med både bruker og firma",
        )

    def test_kun_eget_firma(self):
        """🛑 Kredittdata om kunder er forretningssensitivt — aldri kryss-firma."""
        domene = self.Data._kunde_domene(self.Data)
        firma_ledd = [
            d for d in domene if isinstance(d, (list, tuple)) and d[0] == "company_id"
        ]
        self.assertTrue(firma_ledd, "Mangler company_id — tenant-lekkasje")
        self.assertEqual(firma_ledd[0][2], self.env.company.id)

    def test_kun_bokforte_kundefakturaer(self):
        """Leverandørfakturaer hører til 2.80 (likviditet), ikke 2.70 (kredittrisiko)."""
        domene = self.Data._kunde_domene(self.Data)
        type_ledd = [
            d for d in domene if isinstance(d, (list, tuple)) and d[0] == "move_type"
        ]
        self.assertTrue(type_ledd)
        self.assertNotIn(
            "in_invoice",
            type_ledd[0][2],
            "Leverandørfaktura hører ikke i kredittrisiko per kunde",
        )
        state_ledd = [
            d for d in domene if isinstance(d, (list, tuple)) and d[0] == "state"
        ]
        self.assertEqual(state_ledd[0][2], "posted", "Kun bokførte tall")
