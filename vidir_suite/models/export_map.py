
# -*- coding: utf-8 -*-
from odoo import fields, models
class VidirExportMap(models.Model):
    _name='vidir.export.map'; _description='ERP‑mapping av kategorier'
    company_id=fields.Many2one('res.company', required=True, index=True)
    target=fields.Selection([('tripletex','Tripletex'),('poweroffice','PowerOffice'),('xledger','Xledger'),('fortnox','Fortnox')], required=True)
    category=fields.Char(required=True)
    account_code=fields.Char(required=True)
    _uniq_map = models.Constraint(
        'unique(company_id,target,category)',
        'Unik mapping per selskap, mål og kategori',
    )
