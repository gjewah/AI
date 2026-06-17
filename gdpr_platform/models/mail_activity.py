# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError


class MailActivity(models.Model):
    _inherit = 'mail.activity'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._gdpr_check_activity(vals)
        return super().create(vals_list)

    def _gdpr_check_activity(self, vals):
        res_model = vals.get('res_model') or vals.get('res_model_id')
        res_id = vals.get('res_id')
        if not res_id:
            return

        # Resolve model name from id if needed
        if isinstance(res_model, int):
            model_rec = self.env['ir.model'].sudo().browse(res_model)
            res_model = model_rec.model if model_rec.exists() else None

        if not res_model:
            return

        partner = self._gdpr_resolve_partner(res_model, res_id)
        if partner and partner.x_gdpr_blocked:
            raise UserError(
                _("⚠️ GDPR BLOKKERT: Aktivitet kan ikke opprettes for %(name)s.", name=partner.display_name)
            )

    def _gdpr_resolve_partner(self, res_model, res_id):
        try:
            record = self.env[res_model].sudo().browse(res_id)
            if not record.exists():
                return None
            if res_model == 'res.partner':
                return record
            if hasattr(record, 'partner_id'):
                return record.partner_id
        except Exception:
            pass
        return None
