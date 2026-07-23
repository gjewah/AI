# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = ['account.move', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        compute='_compute_gdpr_blocked',
        store=False,
    )

    @api.depends('partner_id', 'partner_id.x_gdpr_blocked')
    def _compute_gdpr_blocked(self):
        for rec in self:
            rec.x_gdpr_blocked = rec.partner_id.x_gdpr_blocked if rec.partner_id else False

    def action_send_and_print(self, **kwargs):
        for move in self:
            if move.partner_id and move.partner_id.x_gdpr_blocked:
                raise UserError(_(
                    "⚠️ GDPR BLOCKED: Invoice cannot be sent to %(name)s.",
                    name=move.partner_id.display_name,
                ))
        return super().action_send_and_print(**kwargs)
