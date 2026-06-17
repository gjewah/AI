# -*- coding: utf-8 -*-
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
                        "⚠️ GDPR BLOKKERT: %(email)s er blokkert og kan ikke legges til mailing list.",
                        email=email,
                    ))
        return super().create(vals_list)


class MassMailing(models.Model):
    _inherit = 'mailing.mailing'

    def _get_recipients(self):
        res = super()._get_recipients()
        if not res:
            return res
        # Exclude GDPR-blocked partners
        blocked = self.env['res.partner'].sudo().search([
            ('x_gdpr_blocked', '=', True),
            ('email', '!=', False),
        ])
        blocked_emails = set(e.lower() for e in blocked.mapped('email') if e)
        filtered = {rid: email for rid, email in res.items()
                    if email.lower() not in blocked_emails}
        return filtered
