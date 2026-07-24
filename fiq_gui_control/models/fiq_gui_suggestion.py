"""📮 Forslagskasse — ønsker og forbedringer til løsningen.

Realiserer «forslagsboks»-konseptet ([[fiq-ai-devtestprod]]): brukere legger inn
ønsker/forbedringer via den røde postkassen i Kontrollrommet; AI/admin gjennomgår.
"""

from odoo import api, fields, models


class FiqGuiSuggestion(models.Model):
    _name = "fiq.gui.suggestion"
    _description = "FIQ forslag — ønske/forbedring"
    _order = "create_date desc"

    name = fields.Char(string="Kort tittel", required=True)
    description = fields.Text(string="Beskrivelse")
    category = fields.Selection(
        [("onske", "Ønske"), ("forbedring", "Forbedring"), ("feil", "Feil/mangel"), ("annet", "Annet")],
        string="Type",
        default="onske",
        required=True,
    )
    state = fields.Selection(
        [
            ("ny", "Ny"),
            ("vurderes", "Vurderes"),
            ("planlagt", "Planlagt"),
            ("utfort", "Utført"),
            ("avslatt", "Avslått"),
        ],
        string="Status",
        default="ny",
        required=True,
    )
    user_id = fields.Many2one("res.users", string="Foreslått av", default=lambda self: self.env.user, readonly=True)
    company_id = fields.Many2one("res.company", string="Firma", default=lambda self: self.env.company)

    @api.model
    def submit(self, name, description=None, category="onske"):
        """Kall fra Kontrollrommet (OWL): opprett et forslag fra den røde postkassen."""
        name = (name or "").strip()
        if not name:
            return False
        rec = self.create(
            {
                "name": name[:120],
                "description": (description or "").strip() or False,
                "category": category if category in dict(self._fields["category"].selection) else "onske",
            }
        )
        return rec.id
