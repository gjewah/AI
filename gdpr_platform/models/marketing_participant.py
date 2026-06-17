# -*- coding: utf-8 -*-
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
                        "⚠️ GDPR BLOKKERT: %(name)s kan ikke delta i marketing automation.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)

    def _execute_action(self):
        """Skip execution for GDPR-blocked participants."""
        for participant in self:
            if participant.partner_id and participant.partner_id.x_gdpr_blocked:
                participant.write({'state': 'canceled'})
                continue
        return super()._execute_action()
