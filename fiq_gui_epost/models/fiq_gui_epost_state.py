#
# Meldingssenter – per-melding arbeidstilstand + interne notater (V00.05).
# mail.message er delt/flyktig; disse slanke sidecar-modellene lagrer FIQ-arbeidsflyt PÅ en melding:
#   * arbeidsstatus (åpen/pågår/ferdig) – gjør innboksen til en arbeidsflate, ikke bare en liste.
#   * internt notat (team-only) – teamdialog rett på e-posten, USYNLIG for avsender.
# Multicompany: company_id + record rules per firma (se security/fiq_gui_epost_rules.xml).

from odoo import fields, models


class FiqMeldingssenterState(models.Model):
    _name = "fiq.meldingssenter.state"
    _description = "Meldingssenter – arbeidsstatus per melding"

    message_id = fields.Many2one(
        "mail.message", required=True, ondelete="cascade", index=True
    )
    status = fields.Selection(
        [("apen", "Åpen"), ("pagar", "Pågår"), ("ferdig", "Ferdig")],
        default="apen",
        required=True,
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    # Manuell overstyring av tverrgående gruppe (Gjermund 19.07: «hvordan endrer jeg
    # på denne statusen på en e-post?» — svaret var: det kunne du ikke).
    #
    # Gruppene settes av nøkkelord i emnet: «haster», «urgent», «viktig» … Treffer
    # maskinen feil, hadde mennesket ingen vei utenom — en hastesak uten ordet «haster»
    # ble liggende i «Uavklart», og et nyhetsbrev som skrev «viktig» havnet i «Viktig».
    # Samme mønster som paringsfeltene: maskinen gjetter, mennesket kan ikke rette.
    #
    # Overstyringen lagres HER, ikke på meldingen: mail.message er delt og flyktig, og
    # valget skal overleve at nøkkelordlista endres.
    tverr_kode = fields.Char(
        string="Overstyrt gruppe",
        help="Tom = maskinen bestemmer ut fra nøkkelord. Satt = mennesket har bestemt, "
        "og nøkkelordene overstyres for denne meldingen.",
    )
    tverr_av = fields.Many2one("res.users", string="Overstyrt av", readonly=True)
    tverr_dato = fields.Datetime(string="Overstyrt", readonly=True)

    # --- Pinn (Gjermund 24.07.2026) --------------------------------------------
    # «et Pinn som hindrer at mailen forsvinner i mengden»
    #
    # 🔑 Pinn er PERSONLIG, ikke felles. Arbeidsstatus og gruppe sier noe om SAKEN og
    # deles av teamet; en pinn sier «jeg må ikke miste denne av syne» og gjelder bare
    # den som satte den. Ville vi delt den, ville to personer overskrevet hverandre —
    # og en pinn du ikke har satt selv er bare støy.
    #
    # Derfor egen sidecar-modell nedenfor (unik per melding+bruker), ikke et felt her:
    # denne posten er DELT per melding, og et `pinnet`-felt her ville vært felles.


class FiqMeldingssenterPinn(models.Model):
    """Én pinn = én bruker har festet én melding øverst.

    Egen modell fordi pinnen er per BRUKER: `fiq.meldingssenter.state` er delt per
    melding, så et felt der ville gjort pinnen felles for hele teamet.
    """

    _name = "fiq.meldingssenter.pinn"
    _description = "Meldingssenter – pinnet melding (per bruker)"
    _order = "create_date desc"

    message_id = fields.Many2one(
        "mail.message", required=True, ondelete="cascade", index=True
    )
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, required=True, index=True
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )

    # Én pinn per melding per bruker. Uten skranken ville gjentatte klikk på
    # pinne-knappen lagt igjen en rad hver gang.
    _melding_bruker_uniq = models.Constraint(
        "unique(message_id, user_id)",
        "Meldingen er allerede pinnet av denne brukeren.",
    )


class FiqMeldingssenterNote(models.Model):
    _name = "fiq.meldingssenter.note"
    _description = "Meldingssenter – internt notat (team-only) per melding"
    _order = "create_date desc"

    message_id = fields.Many2one(
        "mail.message", required=True, ondelete="cascade", index=True
    )
    body = fields.Text(required=True)
    user_id = fields.Many2one(
        "res.users", default=lambda self: self.env.user, required=True
    )
    company_id = fields.Many2one(
        "res.company", default=lambda self: self.env.company, index=True
    )
