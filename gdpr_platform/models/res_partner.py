# -*- coding: utf-8 -*-
import hashlib
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

GDPR_BLOCK_ERROR = _("⚠️ GDPR BLOKKERT: Denne kontakten kan ikke kontaktes.")


def _gdpr_token(partner_id, email, secret):
    raw = f"{partner_id}:{email}:{secret}"
    return hashlib.sha256(raw.encode()).hexdigest()


class ResPartner(models.Model):
    _inherit = 'res.partner'

    x_gdpr_blocked = fields.Boolean(
        string='GDPR – Ikke kontakt',
        default=False,
        index=True,
        tracking=True,
        copy=False,
    )
    x_gdpr_reason = fields.Text(string='GDPR Begrunnelse', copy=False)
    x_gdpr_date = fields.Datetime(string='GDPR Dato', copy=False, readonly=True)
    x_gdpr_user_id = fields.Many2one(
        'res.users', string='GDPR Ansvarlig', copy=False, readonly=True, ondelete='set null'
    )
    x_gdpr_source = fields.Selection([
        ('manual', 'Manuell'),
        ('unsubscribe', 'Avregistrering'),
        ('api', 'API'),
        ('import', 'Import'),
    ], string='GDPR Kilde', copy=False, readonly=True)
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
        secret = self._gdpr_get_secret()
        return _gdpr_token(self.id, self.email or '', secret)

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
                'opt_out': True,
            })

            # Blacklist email
            if partner.email:
                partner._gdpr_add_to_blacklist()

            # Cancel / delete pending activities
            self.env['mail.activity'].sudo().search([
                ('res_model', '=', 'res.partner'),
                ('res_id', '=', partner.id),
            ]).unlink()

            # Stop marketing automation participants
            partner._gdpr_stop_marketing()

            # Remove from mailing lists
            partner._gdpr_remove_from_mailings()

            # Deactivate portal user (optional – based on system param)
            if self.env['ir.config_parameter'].sudo().get_param(
                'gdpr_platform.deactivate_portal', default='True'
            ) == 'True':
                partner._gdpr_deactivate_portal()

            # Audit log
            self.env['gdpr.log'].sudo().create({
                'partner_id': partner.id,
                'action': 'block',
                'user_id': self.env.uid,
                'source': source,
                'ip_address': ip_address,
                'reason': reason,
            })

            # Chatter message
            partner.message_post(
                body=_(
                    "🔴 <b>GDPR BLOKKERT</b><br/>"
                    "Kilde: %(source)s<br/>"
                    "Begrunnelse: %(reason)s<br/>"
                    "Av: %(user)s",
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
            partner.write({
                'x_gdpr_blocked': False,
                'opt_out': False,
            })

            # Remove from blacklist
            if partner.email:
                self.env['mail.blacklist'].sudo().search([
                    ('email', '=ilike', partner.email),
                ]).action_unblacklist()

            self.env['gdpr.log'].sudo().create({
                'partner_id': partner.id,
                'action': 'unblock',
                'user_id': self.env.uid,
                'source': 'manual',
                'ip_address': ip_address,
            })

            partner.message_post(
                body=_("🟢 <b>GDPR blokkering fjernet</b> av %(user)s", user=self.env.user.name),
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
        existing = Blacklist.search([('email', '=ilike', self.email)], limit=1)
        if not existing:
            Blacklist.create({'email': self.email.lower().strip()})
            self.env['gdpr.log'].sudo().create({
                'partner_id': self.id,
                'action': 'blacklist_add',
                'user_id': self.env.uid,
                'source': self.x_gdpr_source or 'manual',
            })

    def _gdpr_stop_marketing(self):
        self.ensure_one()
        try:
            participants = self.env['marketing.participant'].sudo().search([
                ('partner_id', '=', self.id),
                ('state', 'not in', ['completed', 'canceled']),
            ])
            participants.write({'state': 'canceled'})
        except Exception:
            pass

    def _gdpr_remove_from_mailings(self):
        self.ensure_one()
        try:
            contacts = self.env['mailing.contact'].sudo().search([
                ('email', '=ilike', self.email),
            ])
            contacts.write({'opt_out': True})
            # Remove from subscription lists
            sub_contacts = self.env['mailing.contact.subscription'].sudo().search([
                ('contact_id', 'in', contacts.ids),
            ])
            sub_contacts.unlink()
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
        for vals in vals_list:
            if vals.get('x_gdpr_blocked'):
                vals.setdefault('opt_out', True)
        partners = super().create(vals_list)
        for partner in partners:
            if partner.x_gdpr_blocked:
                partner.sudo()._gdpr_add_to_blacklist()
        return partners

    def write(self, vals):
        blocking = vals.get('x_gdpr_blocked')
        result = super().write(vals)
        if blocking:
            for partner in self:
                partner.sudo()._gdpr_add_to_blacklist()
                partner.sudo().write({'opt_out': True})
        return result

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
