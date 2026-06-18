# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import logging
from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_GDPR_BYPASS_CTX = 'gdpr_bypass'


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def message_post(self, **kwargs):
        if self.env.context.get(_GDPR_BYPASS_CTX):
            return super().message_post(**kwargs)
        # Only block emails — never block internal notes or system messages
        message_type = kwargs.get('message_type', 'comment')
        subtype_xmlid = kwargs.get('subtype_xmlid', '')
        is_note = subtype_xmlid == 'mail.mt_note' or message_type not in ('email', 'comment')
        if not is_note:
            partner = self._gdpr_get_self_partner()
            if partner and partner.x_gdpr_blocked:
                raise UserError(_(
                    "⚠️ GDPR BLOCKED: Email cannot be sent to %(name)s.",
                    name=partner.display_name,
                ))
        return super().message_post(**kwargs)

    def _gdpr_get_self_partner(self):
        try:
            if self._name == 'res.partner':
                return self
            if hasattr(self, 'partner_id') and self.partner_id:
                return self.partner_id
        except Exception:
            pass
        return None

    @api.model
    def message_process(self, model, message, custom_values=None, save_original=False,
                        strip_attachments=False, thread_id=None):
        partner = self._gdpr_resolve_inbound_partner(message)
        if partner and partner.x_gdpr_blocked:
            _logger.info("GDPR: Inbound email blocked for partner %s (%s)", partner.id, partner.email)
            self.env['gdpr.log'].sudo().create({
                'partner_id': partner.id,
                'action': 'inbound_blocked',
                'source': 'inbound_email',
                'note': 'Inbound email rejected – partner is GDPR blocked',
            })
            self._gdpr_send_blocked_autoresponse(partner, message)
            return False
        return super().message_process(
            model, message, custom_values=custom_values,
            save_original=save_original, strip_attachments=strip_attachments,
            thread_id=thread_id,
        )

    def _gdpr_resolve_inbound_partner(self, message):
        try:
            from email.utils import parseaddr
            raw_from = message.get('from', '') if hasattr(message, 'get') else ''
            _, email = parseaddr(raw_from)
            if email:
                return self.env['res.partner'].sudo().search(
                    [('email', '=ilike', email)], limit=1
                )
        except Exception:
            pass
        return None

    def _gdpr_send_blocked_autoresponse(self, partner, original_message):
        try:
            from email.utils import parseaddr
            raw_from = original_message.get('from', '') if hasattr(original_message, 'get') else ''
            _, reply_to = parseaddr(raw_from)
            if not reply_to:
                return
            self.env['mail.mail'].sudo().create({
                'subject': _('GDPR – Contact blocked'),
                'body_html': _(
                    "<p>Your email was received, but this contact is GDPR-blocked.<br/>"
                    "We cannot process your request electronically.</p>"
                ),
                'email_to': reply_to,
                'auto_delete': True,
            }).send()
        except Exception as e:
            _logger.warning("GDPR autoresponse failed: %s", e)
