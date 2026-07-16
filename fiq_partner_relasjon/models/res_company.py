# Copyright 2026 FIQ AS
# License LGPL-3
"""Company branding source.

The Control room shows a logo on a dark bar. Odoo's own company logo is usually drawn
for a light background, so a dark-background variant must remain possible — but it
should be the exception, not the thing you have to fill in for every company.

Hence: the native company logo is the source, and a Control-room-specific override
only wins when someone deliberately uploaded one.
"""
from odoo import api, fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    fiq_brand_logo = fields.Binary(
        string="Brand logo",
        compute="_compute_fiq_brand_logo",
        help="The logo to display for this company: the Control room override when set, "
             "otherwise the company's own logo.",
    )

    @api.depends("logo")
    def _compute_fiq_brand_logo(self):
        # fiq_control_logo lives in fiq_gui_control, which may not be installed: this
        # module must work on a plain Odoo. Read it defensively.
        for company in self:
            override = company._fiq_control_logo_override()
            company.fiq_brand_logo = override or company.logo or False

    def _fiq_control_logo_override(self):
        """Return the Control room's dark-background logo variant, if that module is
        installed and a variant was uploaded for this company."""
        self.ensure_one()
        if "fiq_control_logo" in self._fields:
            return self.fiq_control_logo
        return False
