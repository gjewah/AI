# Part of FIQ AI. Norsk kassasystem — X- og Z-rapport (kassasystemforskrifta § 2-8-2 / § 2-8-3).
{
    "name": "FIQ POS — Norsk kassasystem (X/Z-rapport)",
    "version": "19.0.1.0.3",
    "category": "Accounting/Localizations/Point of Sale",
    "summary": "X- og Z-rapport etter norsk kassasystemforskrift",
    "description": """
Norsk kassasystem — X- og Z-rapport
===================================
Implementerer **kassasystemforskrifta** (FOR-2015-12-18-1616) sine krav til kontrollrapporter:

* **§ 2-8-2 X-rapport** — 26 obligatoriske felt (a–z), uten nullstilling.
* **§ 2-8-3 Z-rapport** — samme innhold, **fortløpende nummerert uten hull**, kan ikke gjenbruke
  et nummer, og kan ikke lages før alle salg er avsluttet.

Nummerserien bruker `ir.sequence` med `implementation="no_gap"` per firma — samme mønster som
Odoos egen franske sertifisering (`l10n_fr_pos_cert`).

**Merk:** dette dekker rapport-kravene. Uforanderlig journal (§ 2-6(2), § 2-7(1)),
SAF-T Kassasystem-eksport (§ 2-7(1)) og kassaskuff-sperrer (§ 2-6(5)) er egne krav.
    """,
    "author": "FIQ as",
    "website": "https://www.fiq.no",
    "license": "OPL-1",
    "depends": [
        "point_of_sale",
        "l10n_no",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/fiq_pos_rapport_views.xml",
    ],
    "installable": True,
    "application": False,
}
