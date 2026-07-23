# Part of FIQ AI. Norsk SAF-T Financial 1.30 import.
{
    'name': 'Norway - SAF-T Import',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'summary': 'Import Accounting Data from Norwegian SAF-T Financial files',
    'description': """
Norsk SAF-T Financial 1.30 — import
===================================
Utvider Odoos generiske `account_saft_import` slik at den leser norske SAF-T Financial-filer
(namespace `urn:StandardAuditFile-Taxation-Financial:NO`), f.eks. eksport fra PowerOffice Go.

To avvik mot den generiske modulen håndteres her:

1. **Kontokode:** norsk SAF-T fyller `AccountID`, mens `StandardAccountID` er TOM.
   Generisk modul kaller `.text` direkte på `StandardAccountID` og krasjer (`AttributeError`).
   Her brukes `AccountID` som fallback.

2. **Kontotype:** norsk SAF-T setter `AccountType` = `GL` på ALLE kontoer (ubrukelig for typing).
   I stedet brukes `GroupingCategory` — den norske regnskapsgrupperingen (NS 4102 / SAF-T-standarden),
   som gir presis kontotype (skiller anleggsmiddel/omløpsmiddel, egenkapital/kort-/langsiktig gjeld).

MVA (`TaxCode` / `TaxInformation`) og bilag (`Journal` / `Transaction` / `Line`) leses av
den generiske modulen uten endring.
    """,
    'depends': [
        'account_saft_import',
        'l10n_no',
    ],
    'data': [],
    'author': 'FIQ',
    # OEEL-1 arves fra account_saft_import (Enterprise) som denne utvider.
    'license': 'OEEL-1',
    'auto_install': False,
}
