# -*- coding: utf-8 -*-
from odoo import api, fields, models


class GdprLog(models.Model):
    _name = 'gdpr.log'
    _description = 'GDPR Audit Log'
    _order = 'date desc'
    _rec_name = 'partner_id'

    partner_id = fields.Many2one('res.partner', string='Contact', ondelete='set null', index=True)
    partner_name = fields.Char(string='Contact Name', help='Preserved even if partner is deleted')
    partner_email = fields.Char(string='Email', help='Preserved even if partner is deleted')
    action = fields.Selection([
        ('block', 'Blocked'),
        ('unblock', 'Unblocked'),
        ('unsubscribe', 'Unsubscribed'),
        ('resubscribe', 'Resubscribed'),
        ('blacklist_add', 'Added to Blacklist'),
        ('blacklist_remove', 'Removed from Blacklist'),
        ('portal_deactivate', 'Portal Deactivated'),
        ('inbound_blocked', 'Inbound Email Blocked'),
    ], string='Action', required=True, index=True)
    user_id = fields.Many2one('res.users', string='Performed By', ondelete='set null')
    date = fields.Datetime(string='Date', default=fields.Datetime.now, index=True)
    source = fields.Selection([
        ('manual', 'Manual'),
        ('unsubscribe', 'Unsubscribe Link'),
        ('api', 'API'),
        ('import', 'Import'),
        ('inbound_email', 'Inbound Email'),
        ('automated', 'Automated Action'),
    ], string='Source', default='manual')
    ip_address = fields.Char(string='IP Address')
    reason = fields.Text(string='Reason')
    note = fields.Text(string='Technical Note')
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            if partner.exists():
                vals.setdefault('partner_name', partner.display_name)
                vals.setdefault('partner_email', partner.email)
        return super().create(vals_list)
