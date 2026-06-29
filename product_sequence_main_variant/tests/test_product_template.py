from odoo.tests.common import TransactionCase


class TestProductTemplate(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template_seq = cls.env.ref("product_sequence_number.product_template_sequence")
        cls.variant_seq = cls.env.ref("product_sequence_number.product_variant_sequence")

    def setUp(self):
        super().setUp()
        self.template_seq._get_current_sequence().number_next = 10
        self.variant_seq._get_current_sequence().number_next = 50

    def test_product_template_param_false(self):
        template = self.env["product.template"].create({"name": "Test Template"})
        self.assertEqual(template.sequence_number, "10")
    
    def test_product_template_param_true(self):
        """Tests the product template's unique code sync with variants.

        This test does the following:

        - Creates a new product template
        - Checks the initial variant's code matches the template
        - Creates a second variant
        - Checks the template code does not change
        - Archives the initial variant
        - Checks the template code updates to match the active variant
        """

        self.env["ir.config_parameter"].sudo().set_param(
            "product_sequence_main_variant.product_template_sequence_number_from_main_variant", "True"
        )

        # Create a product template
        template = self.env["product.template"].create({"name": "Test Template"})
        # Check the related product
        related_product_1 = template.product_variant_ids[0]
        self.assertTrue(related_product_1)

        # Check the related product's sequence_number
        #  is the same as the template's sequence_number
        self.assertEqual(
            template.sequence_number,
            related_product_1.sequence_number,
            "code should be the same",
        )
        # Create another related product.product.
        related_product_2 = self.env["product.product"].create(
            {
                "name": "Test Product 1",
                "product_tmpl_id": template.id,
            }
        )
        self.assertTrue(related_product_2)
        # Check that the template's sequence_number has not changed
        self.assertEqual(
            template.sequence_number,
            related_product_1.sequence_number,
            "code should not change",
        )
        # Archive the first related product.product.
        related_product_1.active = False
        # Check that the template's sequence_number has not changed
        self.assertEqual(
            template.sequence_number,
            related_product_1.sequence_number,
            "code should not change",
        )

        template.main_variant_id = related_product_2
        self.assertEqual(
            template.sequence_number,
            related_product_2.sequence_number,
            "code should not be according to main_variant",
        )
