# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError

# Sonekodene er felles for selskap og ansatt. Verdiene MAA stemme med noeklene i
# rule-parameteren `no_aga_sonesatser` (data/hr_rule_parameters_data.xml) —
# et oppslag paa en sone som ikke finnes der, gir ingen sats.
AGA_SONER = [
    ("1", "Sone I — 14,1 %"),
    ("1a", "Sone Ia — 10,6 % inntil fribeløpet"),
    ("2", "Sone II — 10,6 %"),
    ("3", "Sone III — 6,4 %"),
    ("4", "Sone IV — 5,1 %"),
    ("4a", "Sone IVa — 7,9 %"),
    ("5", "Sone V — 0 %"),
]


class ResCompany(models.Model):
    _inherit = "res.company"

    # HOVEDREGELEN (Skatteetaten): sonen foelger VIRKSOMHETEN, ikke arbeidstakeren
    # — normalt den registrerte underenheten. «Den enkelte underenhet utgjoer en
    # egen beregningsenhet for arbeidsgiveravgift, og underenhetens lokalisering
    # avgjoer hvilken sats som skal anvendes.»
    # I Odoo er selskapet den naermeste ekvivalenten til en beregningsenhet.
    fiq_aga_sone = fields.Selection(
        AGA_SONER,
        string="Sone for arbeidsgiveravgift",
        help="Sonen virksomheten er registrert i. Avgjoer satsen for "
             "arbeidsgiveravgift. Drives virksomhet i flere soner, skal hver "
             "underenhet normalt registreres som eget selskap med egen sone.",
    )

    # Fribeloepet gjelder PER FORETAK PER AAR, ikke per ansatt eller per
    # loennskjoering. Det maa derfor akkumuleres paa selskapsnivaa.
    # Kun relevant for sone Ia og IVa, der redusert sats gjelder inntil
    # differansen mot full sats naar fribeloepet.
    fiq_aga_fribelop_brukt = fields.Monetary(
        string="Fribeløp brukt i år",
        currency_field="currency_id",
        help="Akkumulert differanse mellom full og redusert sats hittil i aar. "
             "Naar denne naar fribeloepet, gjelder full sats for det overskytende. "
             "Nullstilles ved aarsskifte.",
    )

    # Hvilket AAR telleren over gjelder for. Uten dette feltet ville
    # fribeloepet aldri blitt nullstilt — og et foretak i sone Ia ville
    # betalt full sats for resten av sin levetid etter foerste aar.
    # Nullstillingen skjer ved foerste bruk i et nytt aar, ikke via en
    # planlagt jobb: en jobb som ikke kjoerer 1. januar ville gitt feil sats
    # i januar, og feil sats er avviksmelding fra Skatteetaten.
    fiq_aga_fribelop_aar = fields.Integer(
        string="Fribeløpsår",
        help="Aaret det forbrukte fribeloepet gjelder for. Byttes aaret, "
             "nullstilles telleren automatisk ved neste loennskjoering.",
    )

    # OTP — obligatorisk tjenestepensjon. Lovens minstekrav er 2 % av loenn
    # opp til 12 G (OTP-loven § 4), men mange foretak har hoeyere sats gjennom
    # avtale eller tariff. Derfor et FELT per selskap, ikke en fast verdi.
    # Staar det tomt, brukes lovens minstekrav.
    fiq_otp_sats = fields.Float(
        string="OTP-sats (%)",
        digits=(5, 2),
        help="Innskuddssats for obligatorisk tjenestepensjon, i prosent av "
             "loenn opp til 12 G. Lovens minstekrav er 2 %. Tomt felt "
             "betyr at minstekravet brukes.",
    )

    @api.constrains("fiq_otp_sats")
    def _check_fiq_otp_sats(self):
        """OTP-satsen kan ikke settes lavere enn loven tillater.

        🛑 Uten denne sperren kunne noen satt 1 % i god tro — og foretaket
        ville braatt loven uten at noe feilet. Samme klasse som en manglende
        AGA-sone: en stille feil med juridiske foelger.
        """
        minste = self.env["hr.rule.parameter"]._get_parameter_from_code(
            "no_otp_minstesats", fields.Date.context_today(self),
        )
        for company in self:
            if company.fiq_otp_sats and company.fiq_otp_sats < minste:
                raise ValidationError(
                    "OTP-satsen kan ikke være lavere enn lovens minstekrav på "
                    "%s %%. Angitt: %s %%. Se OTP-loven § 4."
                    % (minste, company.fiq_otp_sats)
                )

    def fiq_aga_fribelop_gjenstaaende(self, fribelop, aar):
        """Gjenstaaende fribeloep for `aar`, med automatisk aarsskifte.

        Gjelder telleren et tidligere aar, er den utdatert: hele fribeloepet
        staar til raadighet paa nytt.
        """
        self.ensure_one()
        if self.fiq_aga_fribelop_aar != aar:
            return fribelop
        return max(fribelop - self.fiq_aga_fribelop_brukt, 0.0)
