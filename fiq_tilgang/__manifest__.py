# -*- coding: utf-8 -*-
{
    "name": "FIQ Tilgang",
    "version": "19.0.1.2.0",
    "summary": "Arvede rettigheter (Novell-stil) på taksonomi-treet: Lese/Skrive/Administrere "
               "som arves nedover dokument-etikett-hierarkiet, med eksplisitte brudd. "
               "Global admin på topp og per selskap. Speiler Office/SharePoint-tilgangen.",
    "description": """
FIQ Tilgang – arvede rettigheter
================================
Én samlet tilgangs-governance i Odoo som speiler Office/SharePoint. Ressurs-treet er
dokument-etikett-hierarkiet (documents.tag) som speiler den nummererte taksonomien.

Kjerne
 * Nivåer: Lese, Skrive, Administrere.
 * Global admin på topp (hele konsernet) og Global admin per selskap.
 * Arv à la Novell «Inherited Rights Filter»: effektiv tilgang = arvet fra forelder
   + eksplisitte tildelinger - eksplisitte brudd. Et brudd stopper arven fra forelderen.
 * En regel defineres ÉN gang og arves nedover (ikke duplisert per node).

Utkast 02 – kjerne. Dra-og-slipp-tre (OWL) og M365/Graph-synk kommer i neste iterasjon.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["base", "documents"],
    "data": [
        "security/fiq_tilgang_groups.xml",
        "security/ir.model.access.csv",
        "data/fiq_tilgang_roller.xml",
        "views/fiq_tilgang_views.xml",
    ],
    "application": True,
    "installable": True,
}
