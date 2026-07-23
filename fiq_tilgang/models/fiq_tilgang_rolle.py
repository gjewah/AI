# -*- coding: utf-8 -*-
from odoo import models, fields


class FiqTilgangRolle(models.Model):
    """Rolle (stillingsbetegnelse) i firmaets org-hierarki – menneske-roller, distinkt fra
    AI-rollene. Dra en rolle under en annen for org-kart-struktur (parent_id). Dynamisk:
    firma legger til flere roller etter hvert som brukerdata kommer."""
    _name = "fiq.tilgang.rolle"
    _description = "FIQ Tilgang – rolle (stillingsbetegnelse)"
    _parent_name = "parent_id"
    _parent_store = True
    _order = "sequence, name"

    name = fields.Char("Rolle", required=True, translate=True)
    sequence = fields.Integer(default=10)
    parent_id = fields.Many2one(
        "fiq.tilgang.rolle", "Overordnet rolle", ondelete="cascade", index=True)
    # Odoo 19 tar ikke lenger 'unaccent' på dette feltet (gir UserWarning ved hver lasting).
    # Core skriver selv bare index=True — product/models/product_category.py:22.
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("fiq.tilgang.rolle", "parent_id", "Underroller")
    art = fields.Selection(
        [("intern", "Intern (lisens)"), ("ekstern", "Ekstern (portal)")],
        string="Brukertype", default="intern", required=True)
    group_id = fields.Many2one(
        "res.groups", "Koblet Odoo-gruppe",
        help="Valgfri: Odoo-rettighetsgruppe rollen mapper til.")
    company_id = fields.Many2one(
        "res.company", "Selskap", help="Tomt = generisk (arves av alle firma).")
    bruker_ids = fields.One2many("res.users", "fiq_tilgang_rolle_id", "Brukere med rollen")
