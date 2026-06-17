# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""social.post – filter GDPR-blocked partners from social post targeting."""
from odoo import api, models


class SocialPost(models.Model):
    """social.post GDPR helper: removes blocked partners from audience targeting lists."""

    _inherit = 'social.post'

    def _filter_gdpr_audience(self, partner_ids):
        """Remove GDPR-blocked partners from social post targeting."""
        if not partner_ids:
            return partner_ids
        blocked = self.env['res.partner'].sudo().search([
            ('id', 'in', list(partner_ids)),
            ('x_gdpr_blocked', '=', True),
        ])
        return [pid for pid in partner_ids if pid not in blocked.ids]
