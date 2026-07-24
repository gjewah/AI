#
# E-post-ruting (B5): profil/postkasse → firma-kanalisering.
# fetchmail.server (Exchange-innhentingsprofil) har IKKE firma-felt → dette lille,
# generiske mapping-laget avgjør hvilket FIRMA en innkommende postkasse tilhører,
# så post kanaliseres til riktig tenant (+ evt. eier + standard Documents-mappe).
# Autoritativt for NY post; record_company_id dekker post alt på firma-eid element.
# Generisk for ALLE FIQ AS-kunder, tenant-isolert, per-bruker-samtykke.

from odoo import api, fields, models


class FiqKommProfil(models.Model):
    _name = "fiq.komm.profil"
    _description = "E-postprofil → firma (kanalisering av innkommende post)"
    _order = "company_id, mailbox"

    mailbox = fields.Char(
        string="Postkasse (e-postadresse)",
        required=True,
        index=True,
        help="Adressen posten hentes fra, f.eks. gjermund@fiq.no eller post@firma.no.",
    )
    company_id = fields.Many2one(
        "res.company",
        string="Firma",
        required=True,
        index=True,
        help="Firmaet posten fra denne postkassen kanaliseres til (tenant).",
    )
    owner_user_id = fields.Many2one(
        "res.users",
        string="Eier (per-bruker-samtykke)",
        help="Personlig postkasse = eierens; kun eier ser egen post (GDPR).",
    )
    er_felles = fields.Boolean(
        string="Felles postkasse",
        default=False,
        help="Delt funksjonell postkasse (post@/faktura@) som firmaet eier — "
        "trygt å lese sentralt. Motsatt av personlig per-bruker-postkasse.",
    )
    backend = fields.Selection(
        [
            ("proisp_imap", "PRO ISP web-mail (POP3/IMAP)"),
            ("proisp_mapi", "PRO ISP Hosted Exchange (MAPI)"),
            ("m365", "Microsoft 365 / Exchange Online"),
            ("annet", "Annet"),
        ],
        string="Postkasse-backend",
        default="proisp_imap",
        help="HOVEDSAK = PRO ISP web-mail (ikke M365) for eksterne/system/rolle-kontoer; "
        "hoveddomene forblir på Office. Jf. epost_navnepolicy_UTKAST_01.",
    )
    fetchmail_ref = fields.Char(
        string="Innhentingsprofil (ref)",
        help="Valgfri fritekst-referanse til Odoos innhentingsserver (unngår hard "
        "avhengighet til fetchmail-modulen — kobles hardt senere ved behov).",
    )
    aktiv = fields.Boolean(default=True, index=True)

    _mailbox_uniq = models.Constraint(
        "unique(mailbox, company_id)",
        "Samme postkasse er allerede knyttet til dette firmaet.",
    )

    @api.model
    def finn_firma(self, mailbox):
        """Kanaliser fra kilde: gitt en innkommende postkasse-adresse, returner
        firma-id (+ eier + felles-flagg). Autoritativt for ny post. Returnerer
        {} hvis ukjent (da faller ruting tilbake på record_company_id / manuell)."""
        if not mailbox:
            return {}
        p = self.sudo().search(
            [("mailbox", "=ilike", mailbox.strip()), ("aktiv", "=", True)], limit=1
        )
        if not p:
            return {}
        return {
            "company_id": p.company_id.id,
            "company": p.company_id.display_name,
            "owner_user_id": p.owner_user_id.id or False,
            "er_felles": p.er_felles,
            "backend": p.backend,
        }
