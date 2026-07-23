
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
class VidirGS1(http.Controller):
    @http.route(['/gs1/01/<string:gtin>/21/<string:serial>'], type='http', auth='public', website=True)
    def resolve(self, gtin, serial, **kw):
        DPP=request.env['vidir.dpp.passport'].sudo()
        rec=DPP.search([('gtin','=',gtin),('lot','=',serial)], limit=1)
        if rec: return request.redirect(rec.dpp_url, code=302)
        rec=DPP.search([('gtin','=',gtin)], limit=1)
        if rec: return request.redirect(rec.dpp_url, code=302)
        return request.not_found()
