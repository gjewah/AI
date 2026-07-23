# Copyright 2026 FIQ AS, Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).
from odoo import fields, models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        index=True,
        help="Tomt = delt på tvers av alle selskaper. Satt = kun dette selskapet "
        "(egen signatur/logo per firma).",
    )
