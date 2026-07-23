# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
import hashlib
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


def _gdpr_token(partner_id, email, secret):
    raw = f"{partner_id}:{email}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_gdpr_blocked = fields.Boolean(
        string='GDPR – Do Not Contact',
        default=False,
        index=True,
        tracking=True,
        copy=False,
    )
    x_gdpr_reason = fields.Text(string='GDPR Reason', copy=False)
    x_gdpr_date = fields.Datetime(string='GDPR Date', copy=False, readonly=True)
    x_gdpr_user_id = fields.Many2one(
        'res.users', string='GDPR Responsible', copy=False, readonly=True, ondelete='set null'
    )
    x_gdpr_source = fields.Selection([
        ('manual', 'Manual'),
        ('unsubscribe', 'Unsubscribe'),
        ('api', 'API'),
        ('import', 'Import'),
    ], string='GDPR Source', copy=False, readonly=True)
    x_gdpr_token = fields.Char(string='GDPR Token', copy=False, readonly=True)

    # ------------------------------------------------------------------ #
    #  Core GDPR methods                                                   #
    # ------------------------------------------------------------------ #

    def _gdpr_get_secret(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'gdpr_platform.token_secret', default='gdpr-secret-change-me'
        )

    def _gdpr_compute_token(self):
        self.ensure_one()
        return _gdpr_token(self.id, self.email or '', self._gdpr_get_secret())

    def apply_gdpr_block(self, reason='', source='manual', ip_address=None):
        for partner in self:
            partner = partner.sudo()
            token = partner._gdpr_compute_token()
            partner.write({
                'x_gdpr_blocked': True,
                'x_gdpr_reason': reason,
                'x_gdpr_date': fields.Datetime.now(),
                'x_gdpr_user_id': self.env.uid,
                'x_gdpr_source': source,
                'x_gdpr_token': token,
            })
            # Blacklist email (write() does NOT call this anymore — single call here)
            if partner.email:
                partner._gdpr_add_to_blacklist()
            # Cancel pending activities
            self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'res.partner'),
                ('res_id', '=', partner.id),
            ]).unlink()
            partner._gdpr_stop_marketing()
            partner._gdpr_remove_from_mailings()
            if self.env['ir.config_parameter'].sudo().get_param(
                'gdpr_platform.deactivate_portal', default='True'
            ) == 'True':
                partner._gdpr_deactivate_portal()
            self.env['gdpr.log'].sudo().create({
                'partner_id': partner.id,
                'action': 'block',
                'user_id': self.env.uid,
                'source': source,
                'ip_address': ip_address,
                'reason': reason,
            })
            partner.with_context(gdpr_bypass=True).message_post(
                body=_(
                    "🔴 <b>GDPR BLOCKED</b><br/>"
                    "Source: %(source)s<br/>"
                    "Reason: %(reason)s<br/>"
                    "By: %(user)s",
                    source=dict(partner._fields['x_gdpr_source'].selection).get(source, source),
                    reason=reason or '–',
                    user=self.env.user.name,
                ),
                subtype_xmlid='mail.mt_note',
            )
        return True

    def remove_gdpr_block(self, ip_address=None):
        for partner in self:
            partner = partner.sudo()
            partner.write({'x_gdpr_blocked': False})
            if partner.email:
                self.env['mail.blacklist'].sudo()._remove(partner.email)
            self.env['gdpr.log'].sudo().create({
                'partner_id': partner.id,
                'action': 'unblock',
                'user_id': self.env.uid,
                'source': 'manual',
                'ip_address': ip_address,
            })
            partner.with_context(gdpr_bypass=True).message_post(
                body=_("🟢 <b>GDPR block removed</b> by %(user)s", user=self.env.user.name),
                subtype_xmlid='mail.mt_note',
            )
        return True

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    def _gdpr_add_to_blacklist(self):
        self.ensure_one()
        if not self.email:
            return
        Blacklist = self.env['mail.blacklist'].sudo()
        if not Blacklist.search([('email', '=ilike', self.email)], limit=1):
            Blacklist._add(self.email)
            self.env['gdpr.log'].sudo().create({
                'partner_id': self.id,
                'action': 'blacklist_add',
                'user_id': self.env.uid,
                'source': self.x_gdpr_source or 'manual',
            })

    def _gdpr_stop_marketing(self):
        self.ensure_one()
        try:
            self.env['marketing.participant'].sudo().search([
                ('partner_id', '=', self.id),
                ('state', 'not in', ['completed', 'canceled']),
            ]).write({'state': 'canceled'})
        except Exception:
            pass

    def _gdpr_remove_from_mailings(self):
        self.ensure_one()
        try:
            contacts = self.env['mailing.contact'].sudo().search([
                ('email', '=ilike', self.email),
            ])
            if contacts:
                contacts.write({'opt_out': True})
        except Exception:
            pass

    def _gdpr_deactivate_portal(self):
        self.ensure_one()
        portal_users = self.env['res.users'].sudo().search([
            ('partner_id', '=', self.id),
            ('share', '=', True),
            ('active', '=', True),
        ])
        if portal_users:
            portal_users.write({'active': False})
            self.env['gdpr.log'].sudo().create({
                'partner_id': self.id,
                'action': 'portal_deactivate',
                'user_id': self.env.uid,
                'note': f'Portal users deactivated: {portal_users.mapped("login")}',
            })

    # ------------------------------------------------------------------ #
    #  ORM guards                                                          #
    # ------------------------------------------------------------------ #

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            # Only add to blacklist here — apply_gdpr_block is the full block flow
            if partner.x_gdpr_blocked and partner.email:
                partner.sudo()._gdpr_add_to_blacklist()
        return partners

    def write(self, vals):
        # No side-effects here — apply_gdpr_block() handles all side-effects.
        # write() must stay lean to avoid infinite loops from automated actions.
        return super().write(vals)

    # ------------------------------------------------------------------ #
    #  Token URL helpers                                                   #
    # ------------------------------------------------------------------ #

    def _gdpr_unsubscribe_url(self):
        self.ensure_one()
        token = self._gdpr_compute_token()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base}/gdpr/unsubscribe/{token}?pid={self.id}"

    def _gdpr_block_url(self):
        self.ensure_one()
        token = self._gdpr_compute_token()
        base = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base}/gdpr/block/{token}?pid={self.id}"

    @api.model
    def _gdpr_cron_cleanup(self):
        blocked = self.search([('x_gdpr_blocked', '=', True)])
        for partner in blocked:
            partner._gdpr_stop_marketing()
            try:
                if partner.email:
                    self.env['mailing.contact'].sudo().search([
                        ('email', '=ilike', partner.email),
                        ('opt_out', '=', False),
                    ]).write({'opt_out': True})
            except Exception:
                pass
