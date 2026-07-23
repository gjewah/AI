
# -*- coding: utf-8 -*-
from odoo import fields, models
class VidirCO2Request(models.Model):
    _name='vidir.co2.request'; _description='Vidir CO2 Kalkulator – logg'; _order='create_date desc'
    user_type=fields.Selection([('privat','Privat'),('bedrift','Bedrift')])
    country=fields.Char()
    input_json=fields.Json(); result_json=fields.Json()
    total_t=fields.Float(); credits=fields.Integer()
    partner_id=fields.Many2one('res.partner', string='Kontakt')
