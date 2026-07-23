from odoo import api, fields, models


class ResPartner(models.Model):
    _name = "res.partner"
    _inherit = ["res.partner", "action.goto.documents.mixin"]

    partner_folder_id = fields.Many2one(
        "documents.document",
        string="Contact Internal Folder",
    )
    customer_folder_id = fields.Many2one(
        "documents.document",
        string="Customer Internal Folder",
    )
    supplier_folder_id = fields.Many2one(
        "documents.document",
        string="Supplier Internal Folder",
    )
    shared_folder_id = fields.Many2one(
        "documents.document",
        string="Shared Internal Folder",
    )

    partner_folder_url = fields.Char(
        string="Contact External URL",
        related="partner_folder_id.url",
        readonly=False,
    )
    customer_folder_url = fields.Char(
        string="Customer External URL",
        related="customer_folder_id.url",
        readonly=False,
    )
    supplier_folder_url = fields.Char(
        string="Supplier External URL",
        related="supplier_folder_id.url",
        readonly=False,
    )
    shared_folder_url = fields.Char(
        string="Shared External URL",
        related="shared_folder_id.url",
        readonly=False,
    )

    @api.constrains("partner_folder_url")
    def _constrains_partner_folder_url(self):
        if self.partner_folder_url and not self.partner_folder_id:
            root = "partner_documents_folder.documents_document_partner_folder"
            self.partner_folder_id = self.env["documents.document"].create(
                {
                    "name": self.name,
                    "url": self.partner_folder_url,
                    "type": "folder",
                    "partner_id": self.id,
                    "folder_id": self.env.ref(root).id,
                    "res_model": "res.partner",
                    "res_id": self.id,
                }
            )

    @api.constrains("customer_folder_url")
    def _constrains_customer_folder_url(self):
        if self.customer_folder_url and not self.customer_folder_id:
            root = "partner_documents_folder.documents_document_customer_folder"
            self.customer_folder_id = self.env["documents.document"].create(
                {
                    "name": self.name,
                    "url": self.customer_folder_url,
                    "type": "folder",
                    "partner_id": self.id,
                    "folder_id": self.env.ref(root).id,
                    "res_model": "res.partner",
                    "res_id": self.id,
                }
            )

    @api.constrains("supplier_folder_url")
    def _constrains_supplier_folder_url(self):
        if self.supplier_folder_url and not self.supplier_folder_id:
            root = "partner_documents_folder.documents_document_supplier_folder"
            self.supplier_folder_id = self.env["documents.document"].create(
                {
                    "name": self.name,
                    "url": self.supplier_folder_url,
                    "type": "folder",
                    "partner_id": self.id,
                    "folder_id": self.env.ref(root).id,
                    "res_model": "res.partner",
                    "res_id": self.id,
                }
            )

    @api.constrains("shared_folder_url")
    def _constrains_shared_folder_url(self):
        if not self.customer_folder_id:
            return
        if self.shared_folder_url and not self.shared_folder_id:
            # sequence_number = self.sequence_number if "sequence_number" in self._fields else False
            # shared_name = f"{sequence_number or self.name} - Shared"
            self.shared_folder_id = self.env["documents.document"].create(
                {
                    # "name": shared_name,
                    "name": f"{self.name} (Shared)",
                    "url": self.shared_folder_url,
                    "type": "folder",
                    "partner_id": self.id,
                    "folder_id": self.customer_folder_id.id,
                    "res_model": "res.partner",
                    "res_id": self.id,
                }
            )
