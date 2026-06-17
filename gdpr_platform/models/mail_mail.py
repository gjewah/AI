# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""mail.mail – block outgoing email to GDPR-blocked recipients."""
import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    """mail.mail GDPR guard: cancels outbound mail when any recipient is blocked."""

    _inherit = 'mail.mail'

    @api.model_create_multi
    def create(self, vals_list):
        mails = super().create(vals_list)
        for mail in mails:
            mail._gdpr_check_recipients()
        return mails

    def send(self, auto_commit=False, raise_exception=False):
        for mail in self:
            try:
                mail._gdpr_check_recipients()
            except UserError as e:
                _logger.warning("GDPR: Mail send blocked – %s", e)
                mail.write({'state': 'cancel'})
                continue
        return super().send(auto_commit=auto_commit, raise_exception=raise_exception)

    def _gdpr_check_recipients(self):
        self.ensure_one()
        partners = self.recipient_ids.filtered('x_gdpr_blocked')
        if partners:
            names = ', '.join(partners.mapped('display_name'))
            raise UserError(_(
                "⚠️ GDPR BLOKKERT: E-post kan ikke sendes til følgende kontakter: %(names)s",
                names=names,
            ))

    def _gdpr_inject_footer(self, partner):
        """Return GDPR footer HTML for the given partner."""
        if not partner:
            return ''
        unsubscribe_url = partner._gdpr_unsubscribe_url()
        block_url = partner._gdpr_block_url()
        return (
            '<div style="font-size:11px;color:#888;margin-top:20px;border-top:1px solid #eee;padding-top:10px;">'
            f'<a href="{unsubscribe_url}">Avregistrer deg fra e-postlisten</a> | '
            f'<a href="{block_url}">Blokker all kontakt (GDPR)</a>'
            '</div>'
        )
