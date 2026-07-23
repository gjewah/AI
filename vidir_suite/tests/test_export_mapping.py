# -*- coding: utf-8 -*-
from odoo.tests.common import TransactionCase
class TestExportMapping(TransactionCase):
    def test_mapping_unique(self):
        Map=self.env['vidir.export.map']; company=self.env.company
        Map.create({'company_id':company.id,'target':'tripletex','category':'electricity_kwh','account_code':'4000'})
        with self.assertRaises(Exception):
            Map.create({'company_id':company.id,'target':'tripletex','category':'electricity_kwh','account_code':'4001'})
