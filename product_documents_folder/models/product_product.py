from odoo import api, fields, models


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "action.goto.documents.mixin"]

    product_folder_id = fields.Many2one(
        "documents.document",
        string="Product Internal Folder",
    )
    shared_folder_id = fields.Many2one(
        "documents.document",
        string="Shared Internal Folder",
    )
    product_folder_url = fields.Char(
        string="Product External URL",
        related="product_folder_id.url",
        readonly=False,
    )
    shared_folder_url = fields.Char(
        string="Shared External URL",
        related="shared_folder_id.url",
        readonly=False,
    )

    @api.constrains("product_folder_url")
    def _constrains_product_folder_url(self):
        if not self.env.company.product_folder_id:
            return
        if self.product_folder_url and not self.product_folder_id:
            self.product_folder_id = self.env["documents.document"].create(
                {
                    "name": self.name,
                    "url": self.product_folder_url,
                    "type": "folder",
                    "folder_id": self.env.company.product_folder_id.id,
                    "res_model": "product.product",
                    "res_id": self.id,
                }
            )

    @api.constrains("shared_folder_url")
    def _constrains_shared_folder_url(self):
        if not self.product_folder_id:
            return
        if self.shared_folder_url and not self.shared_folder_id:
            self.shared_folder_id = self.env["documents.document"].create(
                {
                    "name": f"{self.name} (Shared)",
                    "url": self.shared_folder_url,
                    "type": "folder",
                    "folder_id": self.product_folder_id.id,
                    "res_model": "product.product",
                    "res_id": self.id,
                }
            )
