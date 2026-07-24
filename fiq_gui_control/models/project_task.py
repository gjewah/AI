from odoo import fields, models


class ProjectTask(models.Model):
    """🎚 Manuell fremdrifts-overstyring (v6.66): settes fra Kontrollrommets detaljboks.

    🔑 NORSK ER KILDESPRÅKET — engelsk er oversettelsen ([[norsk-spraklinje-er-fasit]]).
    Etiketter OG valgverdier sto på engelsk fram til 24.07.2026 (rest etter 18→19).
    Gjermund: «vi skal ha språk på alle felter og alle feltverdier.» En nedtrekksliste som
    står igjen på feil språk er halvveis oversatt — verre enn ikke oversatt, fordi brukeren
    tror resten er på sitt språk.
    """

    _inherit = "project.task"

    fiq_manual_pct = fields.Float(
        string="Manuell fremdrift (%)",
        help="Manuelt vurdert fremdrift for denne oppgaven. Brukes etter valgt overstyringsmodus.",
    )
    fiq_pct_mode = fields.Selection(
        [
            ("av", "Av (kun timer)"),
            ("erstatt", "Erstatter den timebaserte fremdriften"),
            ("adder", "Legges til den timebaserte fremdriften"),
        ],
        default="av",
        string="Overstyring av fremdrift",
        help="Hvordan den manuelle prosenten kombineres med førte og estimerte timer i Kontrollrommet.",
    )
