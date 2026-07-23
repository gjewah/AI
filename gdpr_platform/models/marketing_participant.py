# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, models, _
from odoo.exceptions import UserError


class MarketingParticipant(models.Model):
    _inherit = 'marketing.participant'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOCKED: %(name)s cannot participate in marketing automation.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)
