# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""gdpr.partner.mixin – reusable block/unblock actions for models with partner_id."""
from odoo import models, _
from odoo.exceptions import UserError


class GdprPartnerMixin(models.AbstractModel):
    """Abstract mixin that adds GDPR block/unblock buttons to any model with partner_id."""

    _name = 'gdpr.partner.mixin'
    _description = 'GDPR Partner Block Mixin'

    def action_gdpr_block_partner(self):
        """Block the linked partner and run all GDPR side-effects."""
        self.ensure_one()
        partner = getattr(self, 'partner_id', None)
        if not partner or not partner.exists():
            raise UserError(_("Ingen kontakt er valgt."))
        partner.sudo().apply_gdpr_block(source='manual')
        return True

    def action_gdpr_unblock_partner(self):
        """Lift the GDPR block on the linked partner."""
        self.ensure_one()
        partner = getattr(self, 'partner_id', None)
        if not partner or not partner.exists():
            raise UserError(_("Ingen kontakt er valgt."))
        partner.sudo().remove_gdpr_block()
        return True
