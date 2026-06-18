# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        sendable = self.env['mail.mail']
        for mail in self:
            blocked = mail.recipient_ids.filtered('x_gdpr_blocked')
            if blocked:
                names = ', '.join(blocked.mapped('display_name'))
                _logger.warning("GDPR: Mail %s cancelled – blocked recipients: %s", mail.id, names)
                mail.write({'state': 'cancel'})
            else:
                sendable |= mail
        if sendable:
            return super(MailMail, sendable).send(
                auto_commit=auto_commit, raise_exception=raise_exception
            )

    def _gdpr_inject_footer(self, partner):
        if not partner:
            return ''
        unsubscribe_url = partner._gdpr_unsubscribe_url()
        block_url = partner._gdpr_block_url()
        return (
            '<div style="font-size:11px;color:#888;margin-top:20px;border-top:1px solid #eee;padding-top:10px;">'
            f'<a href="{unsubscribe_url}">Unsubscribe from mailing list</a> | '
            f'<a href="{block_url}">Block all contact (GDPR)</a>'
            '</div>'
        )
