# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import api, models, _
from odoo.exceptions import UserError


class MailingContact(models.Model):
    _inherit = 'mailing.contact'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            email = vals.get('email', '')
            if email:
                partner = self.env['res.partner'].sudo().search(
                    [('email', '=ilike', email)], limit=1
                )
                if partner and partner.x_gdpr_blocked:
                    raise UserError(_(
                        "⚠️ GDPR BLOCKED: %(email)s is blocked and cannot be added to a mailing list.",
                        email=email,
                    ))
        return super().create(vals_list)
