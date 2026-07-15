from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # A compute method should compute only stored fields or non-stored fields.
    # res_company_search_view makes the address fields stored.
    # base_location adds non-stored fields.
    # To avoid conflicts in the compute method, we make the new fields stored.

    city_id = fields.Many2one(store=True)
    zip_id = fields.Many2one(store=True)
