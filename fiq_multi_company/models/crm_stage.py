# Copyright 2026 FIQ AS, Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class CrmStage(models.Model):
    _inherit = "crm.stage"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="Tomt = delt på tvers av alle selskaper. Satt = kun dette selskapet.",
    )
