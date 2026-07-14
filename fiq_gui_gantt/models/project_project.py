# -*- coding: utf-8 -*-
#
# FIQ GUI Gantt — utvidelse av project.project.
# Kun VISNINGS-status for tid (time_status) til Gantt-pilledekorasjon.
# sequence_code (Project No.) og internal_external RØRES ALDRI — kun lest ved behov.

from odoo import api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    time_status = fields.Selection(
        selection=[
            ("gronn", "I rute"),
            ("oransje", "Bak skjema"),
            ("rod", "Forfalt"),
        ],
        string="Tidsstatus",
        compute="_compute_time_status",
        store=False,
        help="🟢 i rute · 🟠 bak skjema · 🔴 forfalt. Beregnet av utløpsdato og "
             "fullføringsgrad. Brukes til fargedekorasjon i prosjekt-Gantt.",
    )

    def action_open_task_gantt(self):
        """Drill-ned: åpne oppgave-Gantt filtrert på dette prosjektet."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "fiq_gui_gantt.action_project_task_gantt_fiq"
        )
        action["domain"] = [("project_id", "=", self.id)]
        action["display_name"] = "%s — Oppgave-Gantt" % (self.display_name or "")
        action["context"] = dict(
            self.env.context,
            fiq_gantt=True,
            default_project_id=self.id,
            search_default_project_id=self.id,
            # Ingen gruppering på prosjekt siden vi allerede er filtrert til ett.
            group_by=[],
        )
        return action

    @api.depends("date", "date_start", "task_completion_percentage")
    def _compute_time_status(self):
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for project in self:
            status = "gronn"
            slutt = project.date          # Utløpsdato (Date)
            start = project.date_start    # Startdato (Date)
            ferdig = (project.task_completion_percentage or 0.0)  # 0..100
            if slutt and slutt < today and ferdig < 100.0:
                status = "rod"
            elif slutt and slutt == today and ferdig < 100.0:
                status = "oransje"
            elif start and slutt and start <= today <= slutt and slutt > start:
                total = (slutt - start).days
                if total > 0:
                    forventet = (today - start).days / float(total)  # 0..1
                    faktisk = ferdig / 100.0
                    if faktisk + 0.15 < forventet:
                        status = "oransje"
            project.time_status = status
