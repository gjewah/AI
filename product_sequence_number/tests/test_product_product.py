from odoo.tests.common import TransactionCase


class TestProductProduct(TransactionCase):

    def setUp(self):
        super().setUp() # line 18
        self.sequence = self.env['ir.sequence'].search(
            [('code', '=', "product.product"), '|', ('company_id', '=', self.env.company.id), ('company_id', '=', False)],
            order='company_id desc',  # company-specific first, then global
            limit=1
        )
        self.sequence.write(
            {
                "number_next_actual": 1,
            }
        )

    def test_product_product_creation(self):
        product_1 = self.env["product.product"].create({"name": "product 1"})
        id = str(product_1.id).zfill(5)
        self.assertEqual(
            product_1.sequence_number, "1",
        )
