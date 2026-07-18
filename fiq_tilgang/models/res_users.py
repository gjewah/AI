# -*- coding: utf-8 -*-
from odoo import models, fields


class ResUsers(models.Model):
    _inherit = "res.users"

    fiq_tilgang_rolle_id = fields.Many2one(
        "fiq.tilgang.rolle", string="Rolle (stilling)",
        help="Brukerens stillingsrolle i org-hierarkiet (FIQ Tilgang).")
