from odoo import api, fields, models


class ResCityZip(models.Model):
    _inherit = "res.city.zip"

    assign_location_ids = fields.One2many(
        "res.partner.assign.location",
        "zip_id",
        string="Assigned Locations",
    )
