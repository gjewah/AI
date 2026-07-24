from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Per-company branding for the Control room. Generic: every company shares the same
    # dark-grey sidebar; only the accent color + logo vary.
    fiq_control_accent = fields.Char(
        string="Control room accent color",
        default="#38B44A",
        help="Hex color used as the accent in the Control room (active menu, KPI, progress).",
    )
    fiq_control_logo = fields.Binary(
        string="Control room logo (light variant)",
        help="Logo shown in the Control room top bar and sidebar. Use a variant that reads "
        "on a dark background (white/silver) for the sidebar.",
    )
    fiq_control_as_home = fields.Boolean(
        string="Start in Control room",
        default=False,
        help="When ON: internal users in this company get the Control room as their start page. "
        "When OFF: users keep/get back Odoo's standard start page (unlocks). "
        "Admin-controlled — turn on only once the dashboard is verified stable.",
    )
