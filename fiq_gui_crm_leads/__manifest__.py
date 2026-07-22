# -*- coding: utf-8 -*-
{
    "name": "FIQ Salgsmuligheter",
    "version": "19.0.1.4.2",
    "summary": "AI GUI Salg (6 SALG) — visningen av AI Salg-Rådgiveren: pipeline per "
               "stadium med antall og forventet omsetning, lest fra crm.lead.",
    "description": """
FIQ GUI Salg — flate 6 SALG
===========================

Flaten er VISNINGEN av rolla «0.00 6 AI Salg-Rådgiver» (rolle bak, flate foran).
Ingen parallell salgslogikk: pipeline og tall eies av Odoo (native-først).

Innhold (UTKAST 01 — pipeline-oversikt)

 * Nøkkeltall: åpne salgsmuligheter og forventet omsetning.
 * Pipeline per stadium med antall, verdi og andel — stadiene leses fra basen,
   de er ikke en liste i koden. Hvert firma setter opp sine egne.
 * Klikk på et stadium åpner Odoos egen liste, filtrert på det stadiet.
 * Samleboks til Kontrollrommet: forfalte muligheter, forfall i dag, åpen pipeline.

Harde regler innebygd i flaten

 * Åpen pipeline = kun AKTIVE stadier. Vunnet fanges av is_won; tapt har ingen
   tilsvarende markør i Odoo og leses av nummerprefikset 9.99. Uten begge
   telles hver tapt sak som åpen pipeline.
 * Firma hentes fra sesjonen, aldri som parameter fra klienten (tenant-isolasjon).
 * Rådgiver, ikke beslutter — ingen automatiske salgshandlinger.
 * Kun eget firmas salg. Kunde-opplysninger holdes i crm.lead.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    # fiq_gui_shell er IKKE valgfri: uten den er lasterekkefølgen for
    # flate-registeret udefinert. Det var rotårsaken til blank skjerm 18.07.
    "depends": ["fiq_gui_control", "fiq_gui_shell", "web", "crm"],
    "data": [
        "security/fiq_gui_crm_leads_groups.xml",
        "views/fiq_gui_crm_leads_action.xml",
        # Selvregistrering i KR-menyen — MÅ lastes ETTER action-fila (viser til den).
        "data/fiq_gui_salg_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_crm_leads/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
