#
# Meldingssenter – rutingregler (if/then, config-drevet) med audit (V00.05, lag 4).
# Bruker definerer regler i klartekst: «HVIS <felt> <operator> <verdi> → GJØR <handling>».
# Audit: sist kjørt + antall treff per regel. v1 setter arbeidsstatus; utvides senere
# (tildeling, boks-ruting, AI-berikelse). Multicompany: company_id + record rule.

from odoo import fields, models


class FiqKommRegel(models.Model):
    _name = "fiq.komm.regel"
    _description = "Meldingssenter – rutingregel (if/then)"
    _order = "sequence, id"

    name = fields.Char(string="Regelnavn", required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    felt = fields.Selection(
        [
            ("avsender", "Avsender"),
            ("emne", "Emne"),
            ("innhold", "Innhold"),
            ("element", "Element"),
        ],
        string="Felt",
        default="emne",
        required=True,
    )
    operator = fields.Selection(
        [
            ("inneholder", "inneholder"),
            ("er_lik", "er lik"),
        ],
        string="Operator",
        default="inneholder",
        required=True,
    )
    verdi = fields.Char(string="Verdi", required=True)
    handling = fields.Selection(
        [
            ("status_apen", "Sett status: Åpen"),
            ("status_pagar", "Sett status: Pågår"),
            ("status_ferdig", "Sett status: Ferdig"),
        ],
        string="Handling",
        default="status_apen",
        required=True,
    )
    sist_kjort = fields.Datetime(string="Sist kjørt", readonly=True)
    treff = fields.Integer(string="Treff totalt", readonly=True, default=0)
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
