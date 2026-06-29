from odoo import api, models

class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)

        for product in products:
            template = product.product_tmpl_id
            if (
                template.use_main_variant_sequence
                and len(template.product_variant_ids) == 1
                and not template.main_variant_id
            ):
                template.main_variant_id = product

        return products
