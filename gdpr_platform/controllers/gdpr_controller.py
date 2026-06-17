# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""GDPR self-service controller – public unsubscribe and full-block URLs.

Routes:
  /gdpr/unsubscribe/<token>?pid=<id>  – opt-out from mailings
  /gdpr/block/<token>?pid=<id>        – full GDPR block

Tokens are SHA-256 digests tied to partner id + email + system secret.
Token verification uses hmac.compare_digest to prevent timing attacks.
"""
import hashlib
import logging

from odoo import http, _
from odoo.http import request

_logger = logging.getLogger(__name__)


def _verify_token(partner, token):
    """Return True if *token* matches the expected SHA-256 digest for *partner*."""
    secret = request.env['ir.config_parameter'].sudo().get_param(
        'gdpr_platform.token_secret', default='gdpr-secret-change-me'
    )
    expected = hashlib.sha256(
        f"{partner.id}:{partner.email or ''}:{secret}".encode()
    ).hexdigest()
    return hashlib.compare_digest(expected, token)


class GdprController(http.Controller):
    """Public HTTP controller for GDPR self-service actions."""

    # ------------------------------------------------------------------ #
    #  Unsubscribe                                                         #
    # ------------------------------------------------------------------ #

    @http.route('/gdpr/unsubscribe/<string:token>', type='http', auth='public', website=True)
    def gdpr_unsubscribe(self, token, pid=None, **kwargs):
        partner = self._resolve_partner(pid, token)
        if not partner:
            return request.render('gdpr_platform.gdpr_invalid_token', {})

        ip = request.httprequest.remote_addr
        partner.sudo().write({'opt_out': True})
        if partner.email:
            Blacklist = request.env['mail.blacklist'].sudo()
            if not Blacklist.search([('email', '=ilike', partner.email)], limit=1):
                Blacklist.create({'email': partner.email.lower().strip()})
        request.env['gdpr.log'].sudo().create({
            'partner_id': partner.id,
            'action': 'unsubscribe',
            'source': 'unsubscribe',
            'ip_address': ip,
        })

        # Send confirmation email
        self._send_confirmation_email(
            partner,
            subject=_('Du er avmeldt'),
            body=_(
                '<p>Hei,</p>'
                '<p>Du er nå fjernet fra våre e-postlister. Du vil ikke motta markedsføring fra oss.</p>'
                '<p>Kontakt oss direkte hvis du ønsker å abonnere igjen.</p>'
            ),
        )

        return request.render('gdpr_platform.gdpr_unsubscribe_success', {
            'partner_name': partner.name,
        })

    # ------------------------------------------------------------------ #
    #  Full block                                                          #
    # ------------------------------------------------------------------ #

    @http.route('/gdpr/block/<string:token>', type='http', auth='public', website=True)
    def gdpr_block(self, token, pid=None, **kwargs):
        partner = self._resolve_partner(pid, token)
        if not partner:
            return request.render('gdpr_platform.gdpr_invalid_token', {})

        ip = request.httprequest.remote_addr
        if not partner.x_gdpr_blocked:
            partner.sudo().apply_gdpr_block(
                reason=_('Selvbetjening via e-postlenke'),
                source='unsubscribe',
                ip_address=ip,
            )

        self._send_confirmation_email(
            partner,
            subject=_('All kommunikasjon blokkert (GDPR)'),
            body=_(
                '<p>Hei,</p>'
                '<p>Du har nå blokkert all kommunikasjon fra oss i henhold til GDPR.</p>'
                '<p>Vi vil ikke kontakte deg elektronisk. '
                'Kontakt oss skriftlig dersom du ønsker å endre dette.</p>'
            ),
        )

        return request.render('gdpr_platform.gdpr_block_success', {
            'partner_name': partner.name,
        })

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _resolve_partner(self, pid, token):
        """Return partner if pid and token are valid; log and return None otherwise."""
        if not pid or not token:
            return None
        try:
            partner = request.env['res.partner'].sudo().browse(int(pid))
            if not partner.exists():
                return None
            if not _verify_token(partner, token):
                _logger.warning("GDPR: Invalid token for partner %s", pid)
                return None
            return partner
        except Exception as e:
            _logger.error("GDPR token resolution error: %s", e)
            return None

    def _send_confirmation_email(self, partner, subject, body):
        """Send a transient confirmation mail and suppress any send errors."""
        if not partner.email:
            return
        try:
            request.env['mail.mail'].sudo().create({
                'subject': subject,
                'body_html': body,
                'email_to': partner.email,
                'reply_to': request.env['ir.config_parameter'].sudo().get_param(
                    'gdpr_platform.reply_to', default=False
                ),
                'auto_delete': True,
            }).send()
        except Exception as e:
            _logger.error("GDPR confirmation email failed: %s", e)
