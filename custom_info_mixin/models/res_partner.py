from odoo import api, fields, models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["custom.info.mixin", "res.partner"]
