# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    def action_send_and_print(self, **kwargs):
        for move in self:
            if move.partner_id and move.partner_id.x_gdpr_blocked:
                raise UserError(_(
                    "⚠️ GDPR BLOKKERT: Faktura kan ikke sendes til %(name)s.",
                    name=move.partner_id.display_name,
                ))
        return super().action_send_and_print(**kwargs)
