
# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
class VidirReportAPI(http.Controller):
    @http.route(['/dpp/<string:uuid>/report/pdf'], type='http', auth='public')
    def pdf(self, uuid, **kw):
        dpp=request.env['vidir.dpp.passport'].sudo().search([('uuid','=',uuid)], limit=1)
        if not dpp: return request.not_found()
        rep=request.env['vidir.dpp.report'].sudo().create({'name':f'DPP-{dpp.uuid}','partner_id': request.env.user.partner_id.id if request.env.user and request.env.user.partner_id else False,'dpp_id': dpp.id,'grid_country': dpp.country_of_origin or 'NO'})
        rep.action_compute()
        pdf=request.env['ir.actions.report']._render_qweb_pdf('vidir_suite.dpp_customer_report_pdf', res_ids=[rep.id])[0]
        return request.make_response(pdf, [('Content-Type','application/pdf'),('Content-Disposition', f'inline; filename="DPP_Report_{dpp.uuid}.pdf"')])
