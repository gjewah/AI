# -*- coding: utf-8 -*-
from odoo import fields, models


class ProjectTask(models.Model):
    """🎚 Manuell fremdrifts-overstyring (v6.66): settes fra Kontrollrommets detaljboks."""
    _inherit = "project.task"

    fiq_manual_pct = fields.Float(
        string="Manual progress (%)",
        help="Manually assessed progress for this task. Applied according to the progress override mode.")
    fiq_pct_mode = fields.Selection(
        [("av", "Off (hours only)"),
         ("erstatt", "Replaces the hour-based progress"),
         ("adder", "Added on top of the hour-based progress")],
        default="av", string="Progress override",
        help="How the manual percentage is combined with logged/estimated hours in the Control room.")
