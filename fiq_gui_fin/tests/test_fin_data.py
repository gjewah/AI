# -*- coding: utf-8 -*-
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
        cls.produkt = cls.env["product.product"].create({
            "name": "FIQ Testtjeneste FIN",
            "type": "service",
        })

    @classmethod
    def _kunde(cls, navn):
        return cls.env["res.partner"].create({"name": navn})

    @classmethod
    def _faktura(cls, kunde, dager_til_forfall, belop):
        faktura = cls.Move.create({
            "move_type": "out_invoice",
            "partner_id": kunde.id,
            "invoice_date": cls.i_dag,
            "invoice_date_due": fields.Date.add(cls.i_dag, days=dager_til_forfall),
            "invoice_line_ids": [(0, 0, {
                "product_id": cls.produkt.id,
                "quantity": 1,
                "price_unit": belop,
                "tax_ids": [(6, 0, [])],
            })],
        })
        faktura.action_post()
        return faktura

    def _faresignal_navn(self):
        return " ".join(l["tekst"] for l in self.Data.get_kr_boks()["linjer"])

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
            self.assertIn(felt, b, "get_kr_boks mangler kontraktsfeltet %r" % felt)
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

    # ---------- TENANT ----------

    def test_kun_eget_firma(self):
        """🛑 Kredittdata om kunder er forretningssensitivt — aldri kryss-firma."""
        domene = self.Data._kunde_domene(self.Data)
        firma_ledd = [d for d in domene if isinstance(d, (list, tuple))
                      and d[0] == "company_id"]
        self.assertTrue(firma_ledd, "Mangler company_id — tenant-lekkasje")
        self.assertEqual(firma_ledd[0][2], self.env.company.id)

    def test_kun_bokforte_kundefakturaer(self):
        """Leverandørfakturaer hører til 2.80 (likviditet), ikke 2.70 (kredittrisiko)."""
        domene = self.Data._kunde_domene(self.Data)
        type_ledd = [d for d in domene if isinstance(d, (list, tuple))
                     and d[0] == "move_type"]
        self.assertTrue(type_ledd)
        self.assertNotIn("in_invoice", type_ledd[0][2],
                         "Leverandørfaktura hører ikke i kredittrisiko per kunde")
        state_ledd = [d for d in domene if isinstance(d, (list, tuple))
                      and d[0] == "state"]
        self.assertEqual(state_ledd[0][2], "posted", "Kun bokførte tall")
