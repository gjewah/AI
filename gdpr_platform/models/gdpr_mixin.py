# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import models, _
from odoo.exceptions import UserError


class GdprPartnerMixin(models.AbstractModel):
    _name = 'gdpr.partner.mixin'
    _description = 'GDPR Partner Block Mixin'

    def action_gdpr_block_partner(self):
        self.ensure_one()
        partner = getattr(self, 'partner_id', None)
        if not partner or not partner.exists():
            raise UserError(_("No contact is selected."))
        partner.sudo().apply_gdpr_block(source='manual')
        return True

    def action_gdpr_unblock_partner(self):
        self.ensure_one()
        partner = getattr(self, 'partner_id', None)
        if not partner or not partner.exists():
            raise UserError(_("No contact is selected."))
        partner.sudo().remove_gdpr_block()
        return True
