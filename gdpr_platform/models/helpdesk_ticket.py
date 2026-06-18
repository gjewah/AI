# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = ['helpdesk.ticket', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        related='partner_id.x_gdpr_blocked',
        store=True,
        readonly=True,
        index=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOCKED: Helpdesk ticket cannot be created for %(name)s.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)

    def write(self, vals):
        partner_id = vals.get('partner_id')
        if partner_id:
            partner = self.env['res.partner'].sudo().browse(partner_id)
            if partner.exists() and partner.x_gdpr_blocked:
                raise UserError(_(
                    "⚠️ GDPR BLOCKED: Contact %(name)s is blocked.", name=partner.display_name
                ))
        return super().write(vals)
