# Part of FIQ AI.
"""Tester for X- og Z-rapport (kassasystemforskrifta § 2-8-2 / § 2-8-3).

Testene OPPRETTER tilstanden de verner mot — de leser ikke bare eksisterende data.
"""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.addons.point_of_sale.tests.common import TestPoSCommon


@tagged("-at_install", "post_install")
class TestFiqPosRapport(TestPoSCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.basic_config
        cls.produkt = cls.create_product("Testvare", cls.categ_basic, 100.0)

    def _apne_okt(self):
        self.open_new_session()
        return self.pos_session

    def _lag_ordre(self, belop=100.0, antall=1):
        """Oppretter et faktisk avsluttet salg i økta."""
        ordre = self.env["pos.order"].create(
            {
                "session_id": self.pos_session.id,
                "company_id": self.env.company.id,
                "lines": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.produkt.id,
                            "qty": antall,
                            "price_unit": belop,
                            "price_subtotal": belop * antall,
                            "price_subtotal_incl": belop * antall,
                        },
                    )
                ],
                "amount_total": belop * antall,
                "amount_tax": 0.0,
                "amount_paid": belop * antall,
                "amount_return": 0.0,
            }
        )
        ordre.write({"state": "paid"})
        return ordre

    # --- § 2-8-3: nummerserie ------------------------------------------
    def test_z_rapport_nummereres_fortlopende(self):
        """§ 2-8-3 (1): Z-rapporter skal være fortløpende nummerert."""
        okt = self._apne_okt()
        self._lag_ordre()
        forste = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        self._lag_ordre()
        andre = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        self.assertTrue(forste.nummer > 0, "Z-rapport må ha et nummer")
        self.assertEqual(
            andre.nummer,
            forste.nummer + 1,
            "Z-nummer må øke med nøyaktig 1 — ingen hull (§ 2-8-3)",
        )

    def test_z_nummer_kan_ikke_gjenbrukes(self):
        """§ 2-8-3 (2): et Z-nummer kan ikke brukes to ganger."""
        okt = self._apne_okt()
        self._lag_ordre()
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        with self.assertRaises(Exception):
            self.env["fiq.pos.rapport"].create(
                {
                    "type": "z",
                    "session_id": okt.id,
                    "nummer": rapport.nummer,
                    "dato": fields.Datetime.now(),
                }
            )
            self.env.flush_all()

    def test_x_rapport_far_ikke_nummer(self):
        """Bare Z-rapporten er nummerert (§ 2-8-3 mot § 2-8-2)."""
        okt = self._apne_okt()
        self._lag_ordre()
        x = self.env["fiq.pos.rapport"].lag_rapport(okt, "x")
        self.assertEqual(x.nummer, 0, "X-rapport skal ikke tildeles Z-nummer")

    # --- § 2-8-3 (2): alle salg må være avsluttet ----------------------
    def test_z_nektes_nar_salg_er_apent(self):
        """§ 2-8-3 (2): ikke mogeleg å lage Z-rapport før alle sal er avslutta."""
        okt = self._apne_okt()
        self.env["pos.order"].create(
            {
                "session_id": okt.id,
                "company_id": self.env.company.id,
                "amount_total": 50.0,
                "amount_tax": 0.0,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "state": "draft",
            }
        )
        with self.assertRaises(UserError):
            self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

    # --- § 2-6 (2)/(3): sikret mot sletting -----------------------------
    def test_z_rapport_kan_ikke_slettes(self):
        """En avgitt Z-rapport er dokumentasjon og skal ikke kunne fjernes."""
        okt = self._apne_okt()
        self._lag_ordre()
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")
        with self.assertRaises(UserError):
            rapport.unlink()

    # --- § 2-8-2: innhold ----------------------------------------------
    def test_obligatoriske_felt_er_fylt(self):
        """§ 2-8-2 b, c, d: namn, org.nr., dato og kassapunkt-ID."""
        okt = self._apne_okt()
        self._lag_ordre()
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        self.assertTrue(rapport.firma_navn, "b) firmanavn mangler")
        self.assertTrue(rapport.dato, "c) tidspunkt mangler")
        self.assertTrue(rapport.kassapunkt_id_nummer, "d) kassapunkt-ID mangler")

    def test_grand_totals_henger_sammen(self):
        """§ 1-2 o-q: grand total netto = salg minus retur."""
        okt = self._apne_okt()
        self._lag_ordre(belop=100.0)
        self._lag_ordre(belop=250.0)
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        self.assertAlmostEqual(
            rapport.grand_total_netto,
            rapport.grand_total_salg - rapport.grand_total_retur,
            places=2,
            msg="z) grand total netto må være salg minus retur",
        )
        self.assertAlmostEqual(rapport.grand_total_salg, 350.0, places=2)

    def test_spesifikasjonslinjer_opprettes(self):
        """§ 2-8-2 f, g, h, j: fordeling per gruppe, betalingsmiddel, operatør og MVA."""
        okt = self._apne_okt()
        self._lag_ordre()
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        kategorier = set(rapport.linje_ids.mapped("kategori"))
        self.assertIn("hovedgruppe", kategorier, "f) hovedgruppe mangler")
        self.assertIn("operator", kategorier, "h) operatør mangler")

    def test_vekselkasse_tas_med(self):
        """§ 2-8-2 k: inngående vekselkasse."""
        okt = self._apne_okt()
        self._lag_ordre()
        rapport = self.env["fiq.pos.rapport"].lag_rapport(okt, "z")
        self.assertIsNotNone(rapport.inngaende_vekselkasse)

    # --- § 1-2 n: X dekker perioden siden forrige Z ---------------------
    def test_x_dekker_kun_siden_forrige_z(self):
        """§ 1-2 n: X-rapport = registreringar sidan førre Z-rapport."""
        okt = self._apne_okt()
        self._lag_ordre(belop=100.0)
        self.env["fiq.pos.rapport"].lag_rapport(okt, "z")

        self._lag_ordre(belop=75.0)
        x = self.env["fiq.pos.rapport"].lag_rapport(okt, "x")

        self.assertAlmostEqual(
            x.grand_total_salg,
            75.0,
            places=2,
            msg="X-rapport skal kun dekke salg etter forrige Z-rapport",
        )
