
# -*- coding: utf-8 -*-
import uuid as pyuuid
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
class VidirDPP(models.Model):
    _name='vidir.dpp.passport'; _description='Vidir Digital Product Passport'
    name=fields.Char(translate=True)
    uuid=fields.Char(default=lambda s: str(pyuuid.uuid4()), readonly=True, copy=False, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, index=True)
    product_tmpl_id=fields.Many2one('product.template', required=True, ondelete='cascade')
    partner_id=fields.Many2one('res.partner', string='Eier/kunde (valgfritt)')
    gtin=fields.Char(); lot=fields.Char()
    country_of_origin=fields.Char()
    composition=fields.Text(translate=True)
    repairability_score=fields.Float()
    energy_use_kwh_year=fields.Float()
    certificates_json=fields.Text(); extras_json=fields.Text()
    industry_id = fields.Many2one('vidir.industry', string='Bransje')
    industry_profile_id = fields.Many2one('vidir.industry.profile', domain="[('industry_id','=',industry_id),('company_id','=',company_id)]")
    default_marine_fuel_type = fields.Selection([('hfo','HFO'),('mgo','MGO'),('lng','LNG'),('bio','Biofuel'),('methanol','Metanol'),('ammonia','Ammoniakk')], string='Standard maritimt drivstoff')
    default_marine_fuel_ton = fields.Float(string='Standard drivstoffmengde (tonn)')
    dpp_url=fields.Char(compute='_compute_url')
    @api.depends('uuid')
    def _compute_url(self):
        base=self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        for r in self: r.dpp_url=f"{base}/dpp/{r.uuid}"
    @api.constrains('repairability_score')
    def _check_score(self):
        for r in self:
            if r.repairability_score and (r.repairability_score<0 or r.repairability_score>10):
                raise ValidationError(_('Reparerbarhet må være mellom 0 og 10.'))

    def action_open_pdf(self):
        self.ensure_one()
        return {'type':'ir.actions.act_url','url': f"/dpp/{self.uuid}/report/pdf", 'target':'new'}

    def action_export_esg(self):
        self.ensure_one()
        return {'type':'ir.actions.act_url','url': f"/dpp/{self.uuid}/export/xlsx", 'target':'new'}
