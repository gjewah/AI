# -*- coding: utf-8 -*-
{
    "name": "FIQ Komm Ruting — profil→firma",
    "version": "19.0.1.1.0",
    "summary": "E-post-ruting (B5): kanaliser innkommende post til riktig firma ut fra "
               "postkasse/profil. Generisk mapping-lag fordi fetchmail.server mangler firma-felt. "
               "Per-bruker-samtykke (eier) + felles-postkasse-flagg. Tenant-isolert, alle kunder.",
    "description": """
FIQ Komm Ruting — profil→firma (B5)
===================================
Innhentingsprofilene (Exchange/IMAP) i Odoo har ikke firma-felt. Denne modulen gir et
lite, generisk mapping-lag: fiq.komm.profil (postkasse → firma) + finn_firma(mailbox)
som kanaliserer ny post til riktig tenant.

 * Personlig postkasse = eier (per-bruker-samtykke, GDPR — kun eier ser egen post).
 * Felles postkasse (post@/faktura@) = firmaet eier → trygt å lese sentralt.
 * Autoritativt for NY post; record_company_id dekker post alt på firma-eid element.

Del av e-post-ruting-designet (kravfangst B). Generisk for alle FIQ AS-kunder,
tenant-isolert, config-drevet (menneske-redigerbar, ingen kode).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
        "views/fiq_komm_profil_views.xml",
    ],
    "application": False,
    "installable": True,
}
