"""Prosjektets rotmappe i SharePoint — stabil referanse.

Oppgavenes mapper ligger under denne. Merk at SDVs prosjektmappe allerede
navngis av loym-modulen project_fiq (documents_folder_id arver project.name),
og at sp_folder_name der er BEREGNET fra mappas display_name. Feltene her
erstatter ingenting av det — de legger identiteten ved siden av navnet.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    sp_mappe_drive_id = fields.Char(
        string="SP bibliotek-ID",
        index=True,
        copy=False,
        help="Dokumentbiblioteket prosjektmappa ligger i (SDV: 07 PRJ, 02.07 FS m.fl.).",
    )
    sp_mappe_item_id = fields.Char(
        string="SP mappe-ID",
        index=True,
        copy=False,
        help="SharePoint-ID for prosjektets rotmappe. Overlever omdøping — viktig "
        "her, siden mappenavnet arver prosjektnavnet og kan endres.",
    )
    sp_mappe_url = fields.Char(
        string="SP mappe-lenke",
        copy=False,
        help="Nettadresse ved siste synk. Kun visning — ID-en er fasit.",
    )
    sp_har_mappe = fields.Boolean(
        string="Har SP-mappe",
        compute="_compute_sp_har_mappe",
        store=True,
    )

    @api.depends("sp_mappe_drive_id", "sp_mappe_item_id")
    def _compute_sp_har_mappe(self):
        for prosjekt in self:
            prosjekt.sp_har_mappe = bool(
                prosjekt.sp_mappe_drive_id and prosjekt.sp_mappe_item_id
            )

    def sett_sp_mappe(self, drive_id, item_id, web_url=None):
        self.ensure_one()
        if not drive_id or not item_id:
            raise UserError(
                _("Både bibliotek-ID og mappe-ID må oppgis for en stabil referanse.")
            )
        vals = {"sp_mappe_drive_id": drive_id, "sp_mappe_item_id": item_id}
        if web_url:
            vals["sp_mappe_url"] = web_url
        self.write(vals)
        return True
