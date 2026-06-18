# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""mailing.contact / mailing.mailing – exclude blocked contacts from mass mailings."""
from odoo import api, models, _
from odoo.exceptions import UserError


class MailingContact(models.Model):
    """mailing.contact ORM guard: blocks adding a GDPR-blocked email to any mailing list."""

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
                        "⚠️ GDPR BLOKKERT: %(email)s er blokkert og kan ikke legges til mailing list.",
                        email=email,
                    ))
        return super().create(vals_list)


