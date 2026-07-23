# -*- coding: utf-8 -*-
from odoo import fields, models

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
