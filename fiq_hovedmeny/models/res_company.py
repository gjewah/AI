# -*- coding: utf-8 -*-
from odoo import models, fields


class ResCompany(models.Model):
    _inherit = "res.company"

    # Per-firma branding for Hovedmeny Total. Generisk: alle firma deler samme
    # svartgrå sidemeny; kun aksentfargen + logo varierer.
    fiq_hovedmeny_accent = fields.Char(
        string="Hovedmeny aksentfarge",
        default="#38B44A",
        help="Hex-farge brukt som aksent i Hovedmeny Total (aktiv meny, KPI, fremdrift).",
    )
    fiq_hovedmeny_logo = fields.Binary(
        string="Hovedmeny logo (lys variant)",
        help="Logo vist i Hovedmeny-topplinjen og sidemenyen. Bruk en variant som leses "
             "på mørk bakgrunn (hvit/sølv) for sidemenyen.",
    )
    fiq_hovedmeny_as_home = fields.Boolean(
        string="Start i Hovedmeny",
        default=False,
        help="Når PÅ: interne brukere i dette firmaet får Hovedmeny som oppstartsside. "
             "Når AV: brukerne beholder/får tilbake Odoos standard oppstart (låser opp). "
             "Admin-styrt — slå på først når dashbordet er verifisert stabilt.",
    )
