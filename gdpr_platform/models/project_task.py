# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models


class ProjectTask(models.Model):
    _name = 'project.task'
    _inherit = ['project.task', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        related='partner_id.x_gdpr_blocked',
        store=True,
        readonly=True,
        index=True,
    )
