from odoo import api, fields, models


class ResCountryState(models.Model):
    _inherit = "res.country.state"

    assign_location_ids = fields.One2many(
        "res.partner.assign.location",
        "state_id",
        string="Assigned Locations",
    )
