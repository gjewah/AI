
from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"
    _order = "name"

    @api.depends("sequence_code", "name")
    def _compute_sp_folder_name(self):
        for record in self:
            folder = record.documents_folder_id
            if folder:
                record.sp_folder_name = folder.display_name
            else:
                record.sp_folder_name = ""

    sp_folder_name = fields.Char(
        string="SP Folder Name",
        compute="_compute_sp_folder_name",
        help="Sharepoint folder name"
    )
    company_id = fields.Many2one(
        default=lambda self: self.env.company,
        copy=False,
    )

    def _sync_related_records(self, vals=None):
        # Avoid infinite loop
        if self.env.context.get("skip_sync"):
            return
        self = self.with_context(skip_sync=True)

        super()._sync_related_records(vals)

        model_code = (self.env["ir.model"]._get(self._name).code or "").lower()

        for project in self:

            # --- alias_name ---
            # TODO: Write test
            if not vals or "sequence_code" in vals:
                company_code = (project.company_id.code or "").lower()
                project.alias_name = company_code + model_code + project.sequence_code

            # --- documents folder ---
            # TODO: Write test
            if project._fields.get("documents_folder_id") and project.documents_folder_id:
                if not vals or "sequence_code" in vals:
                    if project.documents_folder_id._fields.get("code"):
                        project.documents_folder_id.code = project.sequence_code
                if not vals or "name" in vals:
                    project.documents_folder_id.name = project.name
                    project.documents_folder_id.company_id = project.company_id.id
