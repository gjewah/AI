from odoo import fields, models


class ProjectTaskType(models.Model):
    """FIQ-utvidelse av oppgave-stadiene (Kanban-kolonner): en enkel toggle som
    merker et stadium som del av FIQ AI-arbeidsflyten. Rører IKKE oppgavene eller
    de eksisterende stadiene — bare et flagg. Kontrollrommet kan vise/velge
    AI-stadier ut fra dette. Vi bruker AI-stadiene nå og knytter dem mot de
    øvrige stadiene senere."""

    _inherit = "project.task.type"

    # 🔑 Norsk er kildespråket — engelsk er oversettelsen ([[norsk-spraklinje-er-fasit]]).
    # Sto på engelsk fram til 24.07.2026, en rest etter 18→19-oppgraderingen.
    fiq_ai_stage = fields.Boolean(
        string="AI-stadium",
        help="Merk dette stadiet som en del av FIQ AI-arbeidsflyten. "
        "Kontrollrommet kan da vise og velge AI-stadiene. Endrer ingen oppgaver.",
    )
