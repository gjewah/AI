# -*- coding: utf-8 -*-
import base64, io
from odoo.tests.common import TransactionCase
from openpyxl import Workbook
class TestIndustryFactorImport(TransactionCase):
    def test_import_creates_factors(self):
        Industry=self.env['vidir.industry']
        Profile=self.env['vidir.industry.profile']
        Factor=self.env['vidir.industry.factor.set']
        ind = Industry.create({'name':'Test','code':'test'})
        prof = Profile.create({'name':'Test EU 2026','industry_id':ind.id,'country':'EU','year':2026,'company_id':self.env.company.id})
        wb=Workbook(); ws=wb.active; ws.append(['code','unit','value']); ws.append(['grid_EU','kg/kWh',0.22]); ws.append(['car_diesel','kg/km',0.18])
        bio=io.BytesIO(); wb.save(bio); bio.seek(0)
        wiz=self.env['vidir.industry.factor.import.wizard'].create({'industry_id': ind.id,'profile_id': prof.id,'file_name': 'factors.xlsx','file_data': base64.b64encode(bio.read())})
        wiz.action_import()
        f1=Factor.search([('profile_id','=',prof.id),('code','=','grid_EU')], limit=1)
        f2=Factor.search([('profile_id','=',prof.id),('code','=','car_diesel')], limit=1)
        self.assertTrue(f1 and f2)
        self.assertAlmostEqual(f1.value, 0.22, places=6)
