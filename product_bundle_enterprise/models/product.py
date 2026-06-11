from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_bundle = fields.Boolean("Is Bundle")
    bundle_line_ids = fields.One2many('bundle.line','product_tmpl_id')

class BundleLine(models.Model):
    _name = 'bundle.line'

    product_tmpl_id = fields.Many2one('product.template')
    qty = fields.Float()
    uom_id = fields.Many2one('uom.uom')
    price_factor = fields.Float(default=1.0)
