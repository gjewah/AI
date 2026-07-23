from urllib.parse import urlencode

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    assign_location_ids = fields.One2many(
        "res.partner.assign.location",
        "partner_id",
        string="Assigned Locations",
    )