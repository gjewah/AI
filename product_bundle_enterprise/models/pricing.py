from odoo import models

class BundlePricing(models.AbstractModel):
    _name = 'bundle.pricing'

    def calculate_price(self, product, qty):
        total = 0
        for line in product.bundle_line_ids:
            total += line.qty * line.price_factor
        return total * qty
