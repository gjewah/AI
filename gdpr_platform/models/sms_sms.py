# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SmsSms(models.Model):
    _inherit = 'sms.sms'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner_id = vals.get('partner_id')
            if partner_id:
                partner = self.env['res.partner'].sudo().browse(partner_id)
                if partner.exists() and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOCKED: SMS cannot be sent to %(name)s.",
                        name=partner.display_name,
                    ))
        return super().create(vals_list)

    def send(self, delete_all=False, auto_commit=False, raise_exception=False):
        for sms in self:
            if sms.partner_id and sms.partner_id.x_gdpr_blocked:
                _logger.warning("GDPR: SMS send blocked for partner %s", sms.partner_id.id)
                sms.write({'state': 'canceled'})
        remaining = self.filtered(lambda s: s.state != 'canceled')
        if remaining:
            return super(SmsSms, remaining).send(
                delete_all=delete_all, auto_commit=auto_commit, raise_exception=raise_exception
            )
