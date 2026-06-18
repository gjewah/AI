# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""crm.lead – mirror GDPR fields and block lead creation for blocked contacts."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class CrmLead(models.Model):
    """crm.lead GDPR guard: mirrors x_gdpr_blocked from partner and blocks new leads."""

    _inherit = ['crm.lead', 'gdpr.partner.mixin']

    x_gdpr_blocked = fields.Boolean(
        string='GDPR Blokkert',
        related='partner_id.x_gdpr_blocked',
        store=True,
        readonly=True,
        index=True,
    )
    x_gdpr_reason = fields.Text(
        string='GDPR Begrunnelse',
        related='partner_id.x_gdpr_reason',
        readonly=True,
    )
    x_gdpr_date = fields.Datetime(
        string='GDPR Dato',
        related='partner_id.x_gdpr_date',
        readonly=True,
    )
    x_gdpr_user_id = fields.Many2one(
        'res.users',
        string='GDPR Ansvarlig',
        related='partner_id.x_gdpr_user_id',
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(
                        _("⚠️ GDPR BLOKKERT: Kontakt %(name)s kan ikke kontaktes og det kan ikke opprettes lead.",
                          name=partner.display_name)
                    )
        return super().create(vals_list)

    def write(self, vals):
        partner_id = vals.get('partner_id')
        if partner_id:
            partner = self.env['res.partner'].sudo().browse(partner_id)
            if partner.exists() and partner.x_gdpr_blocked:
                raise UserError(
                    _("⚠️ GDPR BLOKKERT: Kontakt %(name)s er blokkert.", name=partner.display_name)
                )
        return super().write(vals)
