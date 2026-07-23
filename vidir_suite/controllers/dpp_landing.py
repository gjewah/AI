
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
class VidirDPPLanding(http.Controller):
    @http.route(['/dpp/<string:uuid>'], type='http', auth='public', website=True)
    def dpp_landing(self, uuid, **kw):
        rec=request.env['vidir.dpp.passport'].sudo().search([('uuid','=',uuid)], limit=1)
        if not rec: return request.not_found()
        return request.render('vidir_suite.dpp_landing_page', {
          'dpp': rec,
          'json_url': f"/dpp/{uuid}/jsonld",
          'report_pdf_url': f"/dpp/{uuid}/report/pdf",
          'export_xlsx_url': f"/dpp/{uuid}/export/xlsx",
        })
