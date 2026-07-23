
# -*- coding: utf-8 -*-
import json
from odoo import fields, models
from odoo.http import request
class VidirDPPReport(models.Model):
    _name='vidir.dpp.report'; _description='Vidir DPP – Kunderapport'
    name=fields.Char(default=lambda s: 'DPP-rapport')
    partner_id=fields.Many2one('res.partner', string='Kunde')
    year=fields.Char(default=lambda s: str(fields.Date.today().year))
    product_tmpl_id=fields.Many2one('product.template')
    dpp_id=fields.Many2one('vidir.dpp.passport')
    esg_import_id=fields.Many2one('vidir.esg.import')
    prev_report_id=fields.Many2one('vidir.dpp.report')
    manual_json=fields.Text()
    result_json=fields.Text(readonly=True); total_t=fields.Float(readonly=True)
    grid_country=fields.Char(default='NO')
    def action_compute(self):
        self.ensure_one(); payload={"country": self.grid_country or 'NO', "user_type": 'bedrift', "bedrift": {}}
        res=request.env['ir.http']._serve_ir_http_json('/vidir/co2/compute', {'payload': payload})
        self.result_json=res
        try:
            import json
            r=json.loads(res); self.total_t=r.get('total_t') or r.get('activity_t') or 0.0
        except Exception:
            self.total_t=0.0
        return True
