
# -*- coding: utf-8 -*-
from odoo import fields, models
class VidirIndustry(models.Model):
    _name='vidir.industry'; _description='Bransjeregister'
    name=fields.Char(required=True)
    code=fields.Char(index=True)
    active=fields.Boolean(default=True)
class VidirIndustryProfile(models.Model):
    _name='vidir.industry.profile'; _description='Bransjeprofil (land/år)'
    name=fields.Char(required=True)
    industry_id=fields.Many2one('vidir.industry', required=True)
    country=fields.Char()
    year=fields.Integer()
    valid_from=fields.Date(); valid_to=fields.Date()
    company_id=fields.Many2one('res.company', default=lambda s: s.env.company, index=True)
class VidirIndustryFactorSet(models.Model):
    _name='vidir.industry.factor.set'; _description='Faktorsett'; _order='profile_id, code'
    profile_id=fields.Many2one('vidir.industry.profile', required=True, ondelete='cascade')
    code=fields.Char(required=True, index=True)
    unit=fields.Char()
    value=fields.Float()
    source_ref=fields.Char()
    company_id=fields.Many2one('res.company', related='profile_id.company_id', store=True, index=True)
