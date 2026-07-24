{
    "name": "FIQ Dokument SP-ID — stabil SharePoint-referanse på dokument",
    "version": "19.0.1.0.1",
    "summary": "Bærer SharePoints faste drive-/item-ID på documents.document, project.task og "
    "project.project. ID overlever omdøping og flytting — URL gjør ikke. Ren "
    "datamodell: ingen Graph-klient, ingen views, ingen ruting. Fundamentet "
    "dokumentbroen bygger videre på. Generisk, tenant-isolert, config-fri.",
    "description": """
FIQ Dokument SP-ID — LAG 1 av dokumentbroen
=============================================
**Prinsipp (Gjermund 2026-07-05):** SharePoint eier filene — Odoo eier metadata + lenker.
Ingen filer i Odoo-databasen.

Denne modulen gjør ÉN ting: bærer den stabile SharePoint-referansen.

Hvorfor ID og ikke URL
----------------------
En URL peker på hvor fila ligger NÅ (`.../Yttervegger/tilbud.pdf`). Døpes mappa om, eller
flyttes fila, brekker lenken stille. SharePoints `driveItem`-ID overlever begge deler —
URL-en kan regenereres fra ID-en ved behov.

Hvorfor TO felt
---------------
Et driveItem identifiseres av **drive-ID + item-ID**. Item-ID alene er ikke entydig på tvers
av dokumentbibliotek — og SDV har mange (07 PRJ, 02 Tilbud, 01 Leads, 02.07 FS …).

Modeller som utvides
--------------------
 * ``documents.document`` — sp_drive_id, sp_item_id, sp_web_url, sp_sist_synk
 * ``project.task``       — sp_mappe_drive_id, sp_mappe_item_id, sp_mappe_url, sp_mappenavn
 * ``project.project``    — samme fire (prosjektets rotmappe)

Hva modulen IKKE gjør (med vilje)
---------------------------------
Ingen Graph-klient, ingen views/knapper, ingen opplastings-ruting, ingen preview, ingen
deling. Alt det hører i dokumentbroen (``fiq_dokument_sp``), som Gjermund definerer.
Høsting av ID-er kjøres utenfor Odoo og skriver kun disse feltene.

Add-only: ingen eksisterende felt endres eller fjernes. ``documents.document.url``
(loym ``documents_url``) står urørt som sikkerhet.
    """,
    "author": "FIQ AS",
    "website": "https://www.fiq.no",
    "category": "Productivity/Documents",
    "license": "OPL-1",
    "depends": [
        "documents",
        "project",
    ],
    "data": [],
    "installable": True,
    "application": False,
    "auto_install": False,
}
