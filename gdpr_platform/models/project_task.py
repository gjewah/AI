# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        compute='_compute_gdpr_blocked',
        store=False,
    )

    @api.depends('partner_id', 'partner_id.x_gdpr_blocked')
    def _compute_gdpr_blocked(self):
        for rec in self:
            rec.x_gdpr_blocked = rec.partner_id.x_gdpr_blocked if rec.partner_id else False
