# -*- coding: utf-8 -*-
#
# FIQ GUI Gantt — utvidelse av project.milestone.
# Milepæler har kun én dato (deadline). For å vise dem som endagssøyler i Gantt
# avleder vi start/slutt-datotider, og gir dem samme tids-status-farge.

from datetime import datetime, time

from odoo import api, fields, models


class ProjectMilestone(models.Model):
    _inherit = "project.milestone"

    fiq_gantt_start = fields.Datetime(
        string="Gantt start",
        compute="_compute_fiq_gantt_dates",
        store=False,
        help="Avledet starttidspunkt (fristens dato kl. 00:00) — kun for Gantt-visning.",
    )
    fiq_gantt_stop = fields.Datetime(
        string="Gantt slutt",
        compute="_compute_fiq_gantt_dates",
        store=False,
        help="Avledet sluttidspunkt (fristens dato kl. 23:59) — kun for Gantt-visning "
             "(gjør milepælen synlig som en endagssøyle).",
    )
    time_status = fields.Selection(
        selection=[
            ("gronn", "I rute"),
            ("oransje", "Bak skjema"),
            ("rod", "Forfalt"),
        ],
        string="Tidsstatus",
        compute="_compute_time_status",
        store=False,
        help="🟢 nådd / i rute · 🟠 frist i dag · 🔴 forfalt og ikke nådd.",
    )

    @api.depends("deadline")
    def _compute_fiq_gantt_dates(self):
        for m in self:
            if m.deadline:
                m.fiq_gantt_start = datetime.combine(m.deadline, time.min)
                m.fiq_gantt_stop = datetime.combine(m.deadline, time.max)
            else:
                m.fiq_gantt_start = False
                m.fiq_gantt_stop = False

    @api.depends("deadline", "is_reached", "is_deadline_exceeded")
    def _compute_time_status(self):
        today = fields.Date.context_today(self)
        for m in self:
            if m.is_reached:
                m.time_status = "gronn"
            elif m.deadline and m.deadline < today:
                m.time_status = "rod"
            elif m.deadline and m.deadline == today:
                m.time_status = "oransje"
            else:
                m.time_status = "gronn"
