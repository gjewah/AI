from odoo import api, fields, models


class ResCountry(models.Model):
    _inherit = "res.country"

    assign_location_ids = fields.One2many(
        "res.partner.assign.location",
        "country_id",
        string="Assigned Locations",
    )
