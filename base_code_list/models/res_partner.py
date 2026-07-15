from odoo import api, fields, models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["code.list.mixin", "res.partner"]
