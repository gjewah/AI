# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    _inherit = ['crm.lead', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blocked',
        compute='_compute_gdpr_blocked',
        store=True,
        index=True,
    )
    x_gdpr_reason = fields.Text(
        string='GDPR Reason',
        related='partner_id.x_gdpr_reason',
        readonly=True,
    )
    x_gdpr_date = fields.Datetime(
        string='GDPR Date',
        related='partner_id.x_gdpr_date',
        readonly=True,
    )
    x_gdpr_user_id = fields.Many2one(
        'res.users',
        string='GDPR Responsible',
        related='partner_id.x_gdpr_user_id',
        readonly=True,
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
                        "⚠️ GDPR BLOCKED: Contact %(name)s is blocked, cannot create lead.",
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
