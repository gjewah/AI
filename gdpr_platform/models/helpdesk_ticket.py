# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""helpdesk.ticket – block ticket creation for GDPR-blocked contacts."""
from odoo import api, models, _
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    """helpdesk.ticket ORM guard: raises UserError for blocked partners on create and write."""

    _inherit = 'helpdesk.ticket'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOKKERT: Helpdesk-sak kan ikke opprettes for %(name)s.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)

    def write(self, vals):
        partner_id = vals.get('partner_id')
        if partner_id:
            partner = self.env['res.partner'].sudo().browse(partner_id)
            if partner.exists() and partner.x_gdpr_blocked:
                raise UserError(_(
                    "⚠️ GDPR BLOKKERT: Kontakt %(name)s er blokkert.", name=partner.display_name
                ))
        return super().write(vals)
