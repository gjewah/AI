# -*- coding: utf-8 -*-
from odoo.tests.common import HttpCase, tagged
@tagged('-at_install', 'post_install')
class TestJsonLD(HttpCase):
    def test_jsonld_contains_uuid(self):
        dpp=self.env['vidir.dpp.passport'].create({'name':'Prod','product_tmpl_id': self.env['product.template'].create({'name':'P1'}).id,'country_of_origin':'NO'})
        r=self.url_open('/dpp/%s/jsonld' % dpp.uuid)
        self.assertEqual(r.status_code, 200)
        self.assertIn(dpp.uuid, r.text)
