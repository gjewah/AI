from odoo import http
from odoo.http import request

class BundleAPI(http.Controller):

    @http.route('/bundle/calculate', type='json', auth='user')
    def calculate(self, product_id, qty):
        product = request.env['product.template'].browse(product_id)
        price = request.env['bundle.pricing'].calculate_price(product, qty)
        return {"price": price}

    @http.route('/bundle/structure', type='json', auth='user')
    def structure(self, product_id):
        product = request.env['product.template'].browse(product_id)
        lines = []
        for l in product.bundle_line_ids:
            lines.append({
                "qty": l.qty,
                "uom": l.uom_id.name
            })
        return lines
