# Copyright 2026 FIQ AS
# License LGPL-3
"""Partner relation classification + branding source.

Odoo-native first: these are ordinary Odoo fields on res.partner. They are readable
and editable in the standard partner form, with no dependency on the Control room.
The Control room only *reads* them.
"""

from odoo import api, fields, models

# Relation of a partner to the FIQ AI platform. Plain customer by default: a partner
# only becomes an agreement partner by an explicit, deliberate choice.
RELATION_TYPES = [
    ("customer", "Customer"),
    ("agreement_partner", "Agreement partner"),
]

# Graded level for agreement partners. The level says how deep a service relationship
# is; it does NOT by itself grant access to anything (see module docstring).
RELATION_LEVELS = [
    ("1", "1 - Referral"),
    ("2", "2 - Service provider"),
    ("3", "3 - Operations partner"),
    ("4", "4 - Strategic partner"),
]


class ResPartner(models.Model):
    _inherit = "res.partner"

    fiq_relation_type = fields.Selection(
        selection=RELATION_TYPES,
        string="FIQ relation",
        default="customer",
        index=True,
        help="What this partner is to the FIQ AI platform. A plain customer uses the "
        "platform for itself. An agreement partner delivers services to other "
        "customers under an agreement. Classification only — it grants no access.",
    )
    fiq_relation_level = fields.Selection(
        selection=RELATION_LEVELS,
        string="Partner level",
        help="How deep the service relationship is. Only meaningful for agreement "
        "partners. Grants no access on its own: cross-company access requires a "
        "separate two-party agreement per company and domain.",
    )
    fiq_brand_logo = fields.Binary(
        string="Brand logo",
        compute="_compute_fiq_brand_logo",
        help="The logo to display for this partner. Resolves to the partner's own image.",
    )

    @api.depends("image_1920")
    def _compute_fiq_brand_logo(self):
        for partner in self:
            partner.fiq_brand_logo = partner.image_1920 or False

    @api.onchange("fiq_relation_type")
    def _onchange_fiq_relation_type(self):
        """A level only describes an agreement partner; clear it for plain customers."""
        for partner in self:
            if partner.fiq_relation_type != "agreement_partner":
                partner.fiq_relation_level = False
