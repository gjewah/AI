"""Mixin: gir en hvilken som helst modell sjekklister.

Gjermund 19.07.2026: «denne funksjonen kan være på det meste».

Slik kobler en modul seg på — hele jobben er én linje:

    class HelpdeskTicket(models.Model):
        _name = "helpdesk.ticket"
        _inherit = ["helpdesk.ticket", "fiq.sjekkliste.mixin"]

Så legges fanen i visningen (valgfritt, men anbefalt):

    <xpath expr="//notebook" position="inside">
        <page string="Sjekklister" name="fiq_sjekklister">
            <field name="fiq_sjekkliste_fremdrift" widget="progressbar" readonly="1"/>
            <field name="fiq_sjekkliste_ids" nolabel="1"/>
        </page>
    </xpath>

Ingen endring i sjekkliste-motoren kreves. Det er hele poenget med res_model/res_id:
HD, feltservice, salgsmuligheter, utstyr, kontakter — eller en modul som ikke finnes
ennå — kobles på uten at denne koden røres.
"""

from odoo import api, fields, models


class FiqSjekklisteMixin(models.AbstractModel):
    _name = "fiq.sjekkliste.mixin"
    _description = "FIQ Sjekkliste-mixin (gir en modell sjekklister)"

    # Mønsteret er verifisert mot Odoo 19-kildekoden, ikke oppfunnet:
    # `account_move.py:333` gjør One2many('ir.attachment', 'res_id',
    # domain=[('res_model','=','account.move')]), og `mail_activity_mixin.py:49` samme
    # med bypass_search_access. Vi følger begge.
    fiq_sjekkliste_ids = fields.One2many(
        "fiq.sjekkliste",
        "res_id",
        string="Sjekklister",
        domain=lambda self: [("res_model", "=", self._name)],
        bypass_search_access=True,
    )
    fiq_sjekkliste_antall = fields.Integer(
        string="Antall sjekklister",
        compute="_compute_fiq_sjekkliste",
    )
    fiq_sjekkliste_fremdrift = fields.Float(
        string="Sjekkliste utført (%)",
        compute="_compute_fiq_sjekkliste",
        aggregator="avg",
        help="Snitt av sjekklistenes fremdrift.",
    )

    @api.depends("fiq_sjekkliste_ids.fremdrift")
    def _compute_fiq_sjekkliste(self):
        for rec in self:
            lister = rec.fiq_sjekkliste_ids
            rec.fiq_sjekkliste_antall = len(lister)
            rec.fiq_sjekkliste_fremdrift = (
                sum(lister.mapped("fremdrift")) / len(lister) if lister else 0.0
            )

    def apne_sjekkliste_flate(self):
        """Åpne OWL-sjekkliste-flaten for DENNE posten — virker på enhver modell."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "fiq_sjekkliste_flate",
            "name": "Sjekklister",
            "context": {
                "active_model": self._name,
                "active_id": self.id,
                "default_res_model": self._name,
                "default_res_id": self.id,
            },
        }

    def legg_til_sjekkliste_fra_mal(self, mal_id):
        """Kopier en mal til denne posten. Returnerer den nye sjekklista."""
        self.ensure_one()
        mal = self.env["fiq.sjekkliste"].browse(mal_id).exists()
        if not mal:
            return False
        return mal.kopier_til(self._name, self.id)
