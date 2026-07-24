# Copyright 2026 FIQ AS
# License LGPL-3
{
    "name": "FIQ Partner Relations",
    "summary": "Native partner/company relation type, level and branding source "
    "(works without the Control room)",
    "description": """
FIQ Partner Relations
=====================

Native Odoo layer for *who* a partner is to the FIQ AI platform, and where branding
images come from. Deliberately independent of the Control room: per the "Odoo-native
first" canon, every field here is a real Odoo field usable without any FIQ GUI.

Two concerns, one model area (res.partner / res.company):

1. Relation classification (B2B foundation)

   - `fiq_relation_type`: plain customer vs. agreement partner.
   - `fiq_relation_level`: graded level for agreement partners.
   - Opens NO data: this is classification metadata only. Cross-tenant access
     (reading/writing another customer's data) is a separate, later phase that
     requires a two-party agreement + DPA. See docs/0.00 IQ b2b_partner_tilgang_UTKAST_01.md

2. Branding source

   - `fiq_brand_logo`: resolves the logo to use, preferring the native company/partner
     image, with an optional Control-room-specific override for dark backgrounds.
""",
    "version": "19.0.1.1.2",
    "author": "FIQ AS",
    "website": "https://www.fiq.no",
    "license": "OPL-1",
    "category": "FIQ/Base",
    "depends": ["base"],
    # No ir.model.access.csv: this module only adds fields to existing models, so
    # access follows res.partner / res.company.
    "data": [
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
