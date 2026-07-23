
# -*- coding: utf-8 -*-
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo import http
from odoo.http import request
import json

class VidirDPPPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if 'dpp_count' in counters:
            dpp_count = request.env['vidir.dpp.passport'].sudo().search_count([])
            values['dpp_count'] = dpp_count
        return values

    @http.route(['/my/dpps','/my/dpps/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_dpps(self, page=1, **kw):
        DPP = request.env['vidir.dpp.passport'].sudo()
        total = DPP.search_count([])
        pager = portal_pager(url='/my/dpps', total=total, page=page, step=20)
        records = DPP.search([], limit=20, offset=pager['offset'])
        return request.render('vidir_suite.portal_my_dpps', {'records': records, 'pager': pager})

class VidirDPPJsonLD(http.Controller):
    @http.route(['/dpp/<string:uuid>/jsonld'], type='http', auth='public', csrf=False)
    def jsonld(self, uuid, **kw):
        rec = request.env['vidir.dpp.passport'].sudo().search([('uuid','=',uuid)], limit=1)
        if not rec:
            return request.not_found()
        extras=[]
        for name in ['industry','recycled_content_pct','steel_grade','fiber_composition','dye_process','water_use_l_kg','epd_reference','service_life_years','bim_reference','imo_number','vessel_fuel_type','sulfur_pct']:
            if hasattr(rec, name) and getattr(rec, name):
                extras.append({"@type":"PropertyValue","name":name,"value": getattr(rec, name)})
        data = {
            "@context": ["https://schema.org/"],
            "@type": "Product",
            "name": rec.name or (rec.product_tmpl_id and rec.product_tmpl_id.name) or '',
            "gtin": rec.gtin or '',
            "category": rec.product_tmpl_id and rec.product_tmpl_id.categ_id and rec.product_tmpl_id.categ_id.complete_name or '',
            "countryOfOrigin": rec.country_of_origin or '',
            "identifier": [
                {"@type":"PropertyValue","name":"lot_or_serial","value": rec.lot or ""},
                {"@type":"PropertyValue","name":"vidir_uuid","value": rec.uuid}
            ] + extras,
            "url": rec.dpp_url
        }
        body = json.dumps(data, ensure_ascii=False)
        return request.make_response(body, [('Content-Type','application/ld+json; charset=utf-8')])
