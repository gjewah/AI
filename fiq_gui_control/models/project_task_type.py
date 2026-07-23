# -*- coding: utf-8 -*-
from odoo import models, fields


class ProjectTaskType(models.Model):
    """FIQ-utvidelse av oppgave-stadiene (Kanban-kolonner): en enkel toggle som
    merker et stadium som del av FIQ AI-arbeidsflyten. Rører IKKE oppgavene eller
    de eksisterende stadiene — bare et flagg. Kontrollrommet kan vise/velge
    AI-stadier ut fra dette. Vi bruker AI-stadiene nå og knytter dem mot de
    øvrige stadiene senere."""
    _inherit = "project.task.type"

    fiq_ai_stage = fields.Boolean(
        string="AI Stage",
        help="Mark this stage as part of the FIQ AI workflow. "
             "The Control room can then show/select the AI stages. Does not change any tasks.",
    )
