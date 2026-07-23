# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = ['sale.order', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        compute='_compute_gdpr_blocked',
        store=False,
    )

    @api.depends('partner_id', 'partner_id.x_gdpr_blocked')
    def _compute_gdpr_blocked(self):
        for rec in self:
            rec.x_gdpr_blocked = rec.partner_id.x_gdpr_blocked if rec.partner_id else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOCKED: Quotation/order cannot be created for %(name)s.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)
