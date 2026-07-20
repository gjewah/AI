# -*- coding: utf-8 -*-
{
    "name": "FIQ Prosjekt",
    "version": "19.0.1.16.1",
    "summary": "FIQ Prosjekt – WBS-tre med timer mot budsjett (rød ved overforbruk) + "
               "native disposisjonsnummer + generisk sjekkliste-motor (nivå × type, "
               "krav dok/foto/signatur) + OWL sjekkliste-flate. Alt synlig i Odoos egne visninger.",
    "description": """
FIQ GUI Prosjekt
===================
KANON «Odoo-native først» (Gjermund 2026-07-16): KR er et LAG, ikke systemet.
Testen: «Virker dette i native Odoo uten KR?» — feltene her er ekte Odoo-felt
med Odoo-visning. Slås KR av, står de fortsatt.

19.0.1.16.0 — SJEKKLISTER PÅ HVA SOM HELST + MALER (Gjermund 19.07.2026):
 * «både sjekkliste og steg for steg forklaringer skal være redigerbare og kunne
   opprettes på oppgaver, helst også på prosjekter og på HD og Feltservice og
   Salgsmuligheter osv. denne funksjonen kan være på det meste.»
 * GENERISK KOBLING `res_model` + `res_id` (Odoos eget mønster fra ir.attachment /
   mail.activity). Hardkodede felt per modell (task_id, helpdesk_ticket_id, lead_id …)
   ville krevd endring i motoren for HVER ny modul — teknisk gjeld fra dag én.
   Nå kobles en ny modul på uten en eneste kodelinje her.
 * `fiq.sjekkliste.mixin` — en modell får sjekklister med ÉN linje:
   _inherit = ["helpdesk.ticket", "fiq.sjekkliste.mixin"]
   Gir fiq_sjekkliste_ids, fremdrift, antall + apne_sjekkliste_flate().
 * PROSJEKT koblet på nå (fane «Sjekklister» på project.project). HD/feltservice/salg
   kobles på når modulene er der — motoren er allerede klar.
 * 🔴 `task_id` BEHOLDT som computed+store, ikke fjernet: get_wbs_tre() leser
   task.fiq_sjekkliste_ids per node (00.03, 19.07). Ryker task_id, ryker WBS-treet.
   Speiling går BEGGE veier (create/write) så Odoos egne visninger virker uendret.
 * MALER: er_mal + kopier_til(res_model, res_id). «FDV — produktdokumentasjon» skrives
   ÉN gang og kopieres til 50 leiligheter; kopien redigeres fritt uten å røre malen.
   Kvitteringer følger ALDRI med en kopi — å arve andres signatur er utelukket.
 * Migrering 19.0.1.16.0/post-migrate.py fyller res_model/res_id på eksisterende rader
   (SQL, ikke ORM — computen går motsatt vei). Idempotent.

19.0.1.15.0 — WBS-TRE MED TIMER MOT BUDSJETT (kravspek batch 15):

 * TO FEIL RETTET FRA 1.14.0. (1) FLATEN VAR EN LISTEVISNING: tabell over prosjekter
   -> tabell over oppgaver. Gjermund: «du har kun knapt gjenskapt listevisning fra
   Odoo NATIVE!!!» Odoo HAR allerede prosjekter i liste — flaten ga ingen ny verdi.
 * (2) FREMDRIFT BLE KAPPET PÅ 100 %. `min(100.0, (ført/est)*100)` viste 215,9 timer
   mot budsjett 10 som «100 % grønn» — et skjult 22x overforbruk. Å skjule nettopp
   det varselet den som styrer økonomien må se, er ikke en visningsfeil.
   Testen `test_fremdrift_er_alltid_mellom_0_og_100` SEMENTERTE feilen; den er
   erstattet av tester som ville FEILET kappingen.
 * NÅ: foldbart WBS-tre Blokk -> Fase -> Leilighet -> Aktivitet, bygget rekursivt
   fra Odoos EGET project.task-hierarki (parent_id). Ingen ny struktur oppfunnet.
 * Per node: effektive timer / budsjett + fremdriftsbar. Rollup nedenfra —
   forelderens timer = egne + barnas (Odoo tillater timer på forelder med barn).
 * FARGEAKSE (batch 15, linje 198-199) — KOST/timer, ikke frist:
   blå = innenfor budsjett · RØD = OVER budsjett · grønn = ferdig · grå = ikke startet.
   Verste status vinner oppover: ett rødt barn gjør forelderen rød, ellers drukner
   et overforbrukt rom i et prosjekt som «ser fint ut».
   Over budsjett slår ut SELV OM noden er ferdig — en ferdig aktivitet som brukte
   3x budsjettet er ikke en suksess å farge grønn.
 * Stripa klippes visuelt i SCSS (width kan ikke være 2159 %), men TALLET og
   STATUSEN er alltid ærlige. Overforbruk sies dessuten med ord: «+205,9 t over».
 * Firma-bokser øverst (batch 15): konsern-total + ett valg per firma.
 * Visuelt språk hentet fra fasit-mockupen prosjektoversikt_utkast02.html (V00.04):
   samme token-sett, mono-tall med tabular-nums, «X / Y»-mønster, mørk modus.
 * SCSS-fellen `min(px,vw)` (dreper HELE assets-bundelen) unngått bevisst.

19.0.1.4.1 (06.74) — BYGGEFIKS: `expand=`/`string=` på `<group>` i søkevisning er
 Odoo 18-syntaks og gjør visningen ugyldig i 19 -> rødt bygg. Fanget og rettet av
 06.74 mens denne økta bygget videre. Inkludert her.

19.0.1.9.0 — OWL SJEKKLISTE-FLATE (bygg / kvitter):
 * Client action `fiq_sjekkliste_flate` — «penere inngang» til de SAMME dataene.
   KANON Odoo-native først: modellen + native views virker uendret uten flaten.
 * TO MODUSER i ÉN komponent (Gjermund: «PC-eier legger til / mobil-arbeider kvitterer»):
   - bygg    — legg til punkter, veksle krav 📄 dok / 📷 foto / ✍ signatur, slett punkt
   - kvitter — stor hake (hanske/byggeplass), last opp foto/dok, signér
   Modus defaulter fra `user.isInternalUser`, men er togglebar (byggeleder på mobil).
 * Opplasting via KJERNENS `FileInput` -> /web/binary/upload_attachment med
   resModel/resId -> ir.attachment knyttes til punktet, id skrives i kvitt_foto_id/
   kvitt_dok_id. Ingen egen base64-håndtering (verifisert mot web/core/file_input).
 * Krav-constraint RESPEKTERES: kan et punkt ikke kvitteres, er haken sperret og
   «Venter på: dokument + foto» vises. Feiler et forsøk, vises modellens
   ValidationError som varsel — flaten feiler ALDRI stille.
 * Inngangsdører: eget menypunkt · knapp i sjekkliste-skjemaets header (apne_flate)
   · knapp på oppgavens sjekkliste-fane (apne_sjekkliste_flate, filtrerer på oppgaven).
 * RETTIGHETSNØYTRAL: ingen ny res.groups. Arver security fra ir.model.access.csv
   (intern = CRUD, portal = les liste + skriv punkt). Rolle-motoren eier tilgang.
 * Verifisert mot Odoo 19-kilde på Staging: useService fra @web/core/utils/hooks,
   user.isInternalUser/name, luxon global, `and` i t-if (575 treff i core vs 42 `&&`).
   SCSS uten min(px,vw) (den fellen dreper hele assets-bundelen).

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
        "data/fiq_gui_prj_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_prj/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
