# -*- coding: utf-8 -*-
from odoo import api, fields, models


class IrModel(models.Model):
    _inherit = "ir.model"

    code = fields.Char(
        string="Code",
        help="A short code to identify the model. Useful to compute mail aliases who need to be globally unique.",
    )
