# -*- coding: utf-8 -*-
{
    "name": "FIQ Prosjekt",
    "version": "19.0.1.8.0",
    "summary": "FIQ Prosjekt – native disposisjonsnummer (WBS) + generisk sjekkliste-motor "
               "(nivå × type, krav dok/foto/signatur). Alt synlig i Odoos egne visninger.",
    "description": """
FIQ GUI Prosjekt
===================
KANON «Odoo-native først» (Gjermund 2026-07-16): KR er et LAG, ikke systemet.
Testen: «Virker dette i native Odoo uten KR?» — feltene her er ekte Odoo-felt
med Odoo-visning. Slås KR av, står de fortsatt.

19.0.1.4.1 (06.74) — BYGGEFIKS: `expand=`/`string=` på `<group>` i søkevisning er
 Odoo 18-syntaks og gjør visningen ugyldig i 19 -> rødt bygg. Fanget og rettet av
 06.74 mens denne økta bygget videre. Inkludert her.

19.0.1.5.0 — NATIVE MENYPUNKT (flaten var UÅPNELIG):
 * Modulen hadde INGEN menypunkter, og KR-skallet lenket ikke til flaten (grep: 0 treff)
   -> «FIQ Prosjekt» var registrert som klient-handling, men uten dør inn.
 * Nå: toppmeny «FIQ Prosjekt» → «Prosjektoversikt» (flaten) + «Sjekklister».
 * AI PK-avgjørelse 2026-07-17: hver flate-eier legger EGET native menypunkt.
   «Er KR et LAG, kan det ikke være eneste dør inn — da blir KR et single-point-of-failure
   for tilgjengelighet.» KR-sidemenyen kommer i TILLEGG (06.74), ikke som forutsetning.
 * web_icon låner Odoos eget project-ikon (modulen har ingen egen icon.png — verifisert).

19.0.1.4.0 — GENERISK SJEKKLISTE-MOTOR:
 * `fiq.sjekkliste` + `fiq.sjekkliste.punkt` — ÉN motor, ulik mottaker/flate.
   NIVÅ: firma · prosjekt · fase/port · oppgave · rom/objekt · leveranse (UE).
   TYPE: arbeid · KS · våtrom · SHA · FDV · klima · avvik · endring.
 * KRAV er UAVHENGIGE (Gjermund 16.07.2026): dok / foto / signatur.
   FDV og klima ER dokumenter — ikke bilder. Kun avvik/endring er bilde og/eller dokument.
 * Punkt kan ikke kvitteres ut før ALLE krav er levert (constraint + `mangler`-felt).
 * Punkt-tittel/beskrivelse er `translate=True` — ellers får den polske snekkeren norsk
   (samme feil som Vidir 2382: engelsk sjargong -> 0 dokumenter levert).
 * ISO 9001: versjon bumpes ved hver endring.
 * Portal-tilgang: arbeider/UE kan kvittere uten Odoo-lisens (`kvitt_av` = Char).
 * Fane «Sjekklister» på oppgaven + egen liste/skjema/søk med gruppering.
 * ANTI-FORVEKSLING: dette er IKKE fiq_project_checklist (KS/våtrom = eget spor).

19.0.1.3.0:
 * NYTT native felt `fiq_wbs_number` på project.task — dynamisk disposisjonsnummer
   (01, 01.02). Rekalkuleres ved flytting i treet; store+indeksert.
 * Synlig i Odoos EGNE views: liste (optional=show), skjema, søk/gruppering.
 * Nummer-modellen respektert: `code` (oppgavenr.) og `sequence_code` (prosjektnr.)
   er STABILE og røres aldri — kun WBS er dynamisk.

Fra før:
 * OWL klient-handling «FIQ GUI Prosjekt» (placeholder-flate).
 * Rettighetsgruppe (arver base.group_user).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["fiq_gui_control", "web", "project"],
    "data": [
        "security/fiq_gui_prj_groups.xml",
        "security/ir.model.access.csv",
        "views/fiq_gui_prj_action.xml",
        "views/project_task_views.xml",
        "views/fiq_sjekkliste_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_prj/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
