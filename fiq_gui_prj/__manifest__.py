# -*- coding: utf-8 -*-
{
    "name": "FIQ Prosjekt",
    "version": "19.0.1.27.0",
    "summary": "FIQ Prosjekt – WBS-tre med timer mot budsjett (rød ved overforbruk) + "
               "native disposisjonsnummer + generisk sjekkliste-motor (nivå × type, "
               "krav dok/foto/signatur) + OWL sjekkliste-flate. Alt synlig i Odoos egne visninger.",
    "description": """19.0.1.24.0 - TOUCH-MAAL PAA MOBILFLATEN (44px minstemaal):

* AI KR meldte at mobilflate for arbeider manglet helt. MAALT: den FINNES (sjekkliste_flate, deres arbeid) med bygg/kvitter-modus, portal-default og store trykkflater. Det som manglet var STOERRELSEN.
* Haken var 34px (40px paa mobil). 44px er minstemaal for touch (Apple HIG + Material). En snekker med hansker bommer paa 34px - og bommer han, treffer han raden UNDER og kvitterer feil punkt uten aa merke det.
* Haken: 34 -> 44px, mobil 40 -> 52px. Opplastingsknapp: min-height 44px, mobil 48px.
* Rort AI KRs fil (sjekkliste_flate.scss) - kun stoerrelser, ingen logikk. Meldt dem.

19.0.1.23.0 - SJEKKLISTA KOBLET INN I FLATEN (AI KRs sidemannskontroll):

* AI KR maalte 22.07: 0 treff paa sjekkliste i prj.xml OG prj.js. Datalaget (get_sjekklister, 1.21.0) var bygget og MELDT som levert - men aldri koblet paa. Gjermund kunne ikke naa den.
* Noeyaktig samme klasse som resten av uka: bygget riktig, aldri koblet paa. Jeg har kritisert andre for dette og gjorde det selv.
* NAA: sjekkliste-knapp per oppgaverad i alle tre visninger, vises kun naar oppgaven faktisk HAR lister. Aapner sjekkliste-flaten med active_model/active_id - kontrakten verifisert i deres kode, linje 85-88.
* TIL STEDE NAA: bevisst IKKE bygget her. Verifisert i fiq_gui_shell/static/src/shell.xml:6-10 at skallet eier presence-linja med ekte data fra KRs get_presence. To baand ville kunnet vise ulike tall for samme oeyeblikk.
* MOBILFLATE for arbeider staar fortsatt igjen - stoerste gjenstaaende bit i fasiten.

19.0.1.22.0 - BROEN TIL AI KR GAAR NAA BEGGE VEIER:

* Avtalt med AI KR 22.07. Flaten LESER naa context: aktiv_visning (gantt/liste/kanban), opplosning (uke/mnd), task_id, fra. AI KRs fem knapper lander riktig sted.
* Verdiene VALIDERES mot lovlige lister. En ukjent visning ville gitt tom flate uten feilmelding - brukeren saa en hvit rute uten aa vite hvorfor. Ugyldig faller til default.
* task_id markerer raden, filtrerer den IKKE. Filtrering ville fjernet konteksten brukeren kom for aa se.
* TILBAKE: AI KR-merke paa hver AI-utfoert rad i alle tre visninger + KPI Gjort av AI klikkbar til AI KR. Konteksten foelger med (task_id + menyValg), saa han lander paa samme oppgave.

19.0.1.21.0 - SJEKKLISTE-PANELET KOBLET PAA MOTOREN:

* get_sjekklister(oppgave_id) - datalaget for sprettopp-panelet i fasiten (utkast03).
* Fasiten viser EEN liste med TO flater: Prosjekteier legger til punkter, Arbeider kvitterer ut uten Odoo-lisens.
* Dette laget LESER bare. Motoren fiq.sjekkliste (AI KRs arbeid) eier all logikk: krav-constraint, versjonsbump, maler, kvittering. Vi gjenskaper ingenting.
* Kravene er UAVHENGIGE: dok / foto / signatur. Flaten VISER motorens sperre (kan_kvitteres + mangler) i stedet for aa finne opp sin egen.
* 3 nye tester, en av dem oppretter en liste med ukvitterbart punkt og krever at sperren er synlig (port 6).

19.0.1.20.0 - TAALER AT VALGFRIE NABOMODULER MANGLER (fanget paa DEV):

* Foerste kjoering paa DEV_AI_FIQ_01 ga 2 feil som Staging ALDRI viste:
* KeyError planned_date_begin i domenet - feltet kommer fra project_enterprise, som er uninstalled paa Dev.
* AttributeError code i test_wbs - feltet kommer fra project_sequence_number, ogsaa uninstalled.
* Staging har begge installert, saa feilene var usynlige der. Det er hele grunnen til at Dev-leddet finnes: en modul som er groenn mot en RIK base kan vaere ubrukelig paa en mager.
* KANON Odoo-native foerst betyr ogsaa uten TILLEGGSMODULER, ikke bare uten KR.
* FIKS: felt-sjekk foer bruk (planned_date_begin, code). Domenet bygges dynamisk - uten Enterprise faller start-leddet bort, frist-leddet staar.
* Testen hopper over i stedet for aa feile naar en valgfri nabomodul mangler.


FIQ GUI Prosjekt
===================
KANON «Odoo-native først» (Gjermund 2026-07-16): KR er et LAG, ikke systemet.
Testen: «Virker dette i native Odoo uten KR?» — feltene her er ekte Odoo-felt
med Odoo-visning. Slås KR av, står de fortsatt.

19.0.1.19.1 — GANTT VISTE 379 RADER UTEN SOEYLE:

* Maalt paa fiqas Staging 22.07: av 400 returnerte oppgaver kunne bare 21 TEGNES. 379 hadde verken planned_date_begin eller date_deadline.
* ROTAARSAK: domenet hadde ("date_deadline", "=", False) som eget OR-ledd — «ta med alt uten frist». Gantt-en saa nesten tom ut, og KPI-ene summerte til 21 av 400 (resten falt i «plan» uten aa bety noe).
* 🔑 FEILEN VAR USYNLIG I ALLE TIDLIGERE TESTER: metoden svarte 200, returnerte 400 rader, ingen exception. Groenn paa hvert maal vi hadde — og likevel ubrukelig.
* NAA: oppgaven maa ha MINST EEN dato, og den maa beroere vinduet. Udaterte oppgaver finnes fortsatt i Liste/Kanban via get_prosjektoversikt og get_wbs_tre.
* NY TEST test_gantt_returnerer_bare_TEGNBARE_oppgaver.

19.0.1.19.0 — REGISTRERT I KR-SKALLET (flaten kan endelig aapnes):

* registry.category("fiq_gui_flates").add("prj", {...}) — slot-fiksen (KR 6.95) gjoer at runAction() bytter INNMAT, ikke hele siden. Rammen (meny, firmavelger, «Til stede naa») blir staaende. Flaten bygges EEN gang og virker baade i KR og frittstaaende.
* KONTRAKTEN verifisert i kilden (fiq_gui_shell/static/src/shell.js:44-58) FOER registrering: key/label/Component paakrevd, color/sequence valgfrie.
* label som REN TEKST. Begge former er lovlige naa, men det var nettopp dette feltet som felte hele grensesnittet 21.07 — skjemaet krevde tekst mens en kommentar i samme fil sa «begge former». Jeg velger formen som aldri har feilet.
* ⚠️ add() kaster i KALLERENS modul (registry.js:100-101), ikke i skallet. En ugyldig oppfoering ville tatt ned MIN modul under lasting — og med den hele modulgrafen. Derfor staar registreringen sist i fila, etter at alt annet er definert.
* 🔑 FIRMA FRA SKALLET TAS NAA I BRUK: sloten sender {firm, har000, label}, og firm er en ekte res.company-ID. Uten dette ville firmavelgeren i rammen vaert DOED for min flate — brukeren bytter firma oeverst og innholdet staar uendret. Verre enn ingen velger: han tror han ser 051 SDVp mens han ser alt. Verdien SNEVRER kun INN; serveren avgjoer hva som er lov.
* sequence 40 i BAADE data/fiq_gui_prj_flate.xml og JS-registreringen — ellers staar flaten ett sted i menyen og et annet i skallet.

19.0.1.18.5 — DOMENEGRENSER: frist sent paa dagen forsvant STILLE:

* Meldt av KR 22.07. planned_date_begin og date_deadline er Datetime i Odoo 19, men domenet fikk rene date-objekter. Odoo tolker dem som MIDNATT.
* Maalt i basen 22.07: <= date(2026,7,21)               -> 463 <= datetime(2026-07-21 00:00:00) -> 463   (identisk = midnatt) <= datetime(2026-07-21 23:59:59) -> 463 I dag er tallene like fordi ALLE frister staar paa midnatt (0 med klokkeslett). Foerste gang noen setter frist kl. 15:00, forsvinner den ut av siste kolonne — uten feilmelding, uten at noen merker det.
* FIKS: datetime.combine(start, min.time()) og datetime.combine(slutt, max.time()). Merk max.time() paa slutten — min.time() ville kuttet siste dag ved midnatt.
* Samme klasse som Kommunikasjons fredags-frister som forsvant fra ukesplanen (fiq_gui_epost_data.py, _ukesplan_for_partner). Tredje gang i huset.
* NY TEST test_frist_sent_paa_dagen_forsvinner_ikke oppretter en oppgave med frist kl. 15:00 paa siste dag i vinduet og krever at den er med.

📌 MERK: TypeError-krasjet KR viste til var allerede rettet i 1.18.4. Loggen var fra
22:58, fiksen kom 23:15. Metoden kjoerer naa: 400 oppgaver, begge akser. Men KR pekte
paa en ekte risiko i domenet som staar igjen — den rettes her.

19.0.1.18.4 — FIKS AV EGEN FIKS: NameError i get_oppgaver:

* 1.18.3 rettet Datetime/Date-blandingen med et globalt soek-og-erstatt. Det traff ogsaa get_oppgaver, der variabelen frist_d ikke finnes: NameError: name 'frist_d' is not defined  (linje 591) To eldre tester gikk fra groenn til ERROR.
* Fanget av testkjoering FOER melding — 0 failed, 2 error(s) av 43.
* LAERDOM: soek-og-erstatt paa tvers av funksjoner er ikke trygt naar erstatningen viser til en lokal variabel. Rettet med eksplisitt frist_dato i den funksjonen, og verifisert maskinelt (AST) at ingen funksjon bruker en udefinert frist-variabel.

19.0.1.18.3 — HASTEFIKS: Datetime/Date-blanding felte flaten (feilklasse 8):

* fiqas Staging 21.07 kl. 22:58, etter rebuild fra Production: TypeError: can't compare datetime.datetime to datetime.date fiq_gui_prj_data.py:243  ->  if frist < i_dag get_oppgaver_over_tid ga 500 -> flaten fikk ingen data -> BLANK SKJERM.
* ROTAARSAK: date_deadline og planned_date_begin er **Datetime** i Odoo 19 (verifisert i kilden: project/models/project_task.py:183 + project_enterprise/ models/project_task.py:26, og i ir_model_fields = «datetime»), mens fields.Date.context_today() gir en **Date**. Sammenligningen er ulovlig.
* RETTET FIRE STEDER, ikke bare de to som krasjet: _tid_status (sammenligning + differanse), e i radbyggingen (blandet Datetime og Date i samme rad), og to Date.to_string-kall som fikk Datetime inn.
* 🔑 HVORFOR 42 GROENNE TESTER IKKE FANGET DET: koden returnerte paa «if not frist» naar ingen oppgave hadde frist. Paa tynn base ble sammenligningen ALDRI naadd. Etter rebuild fra Production fantes ekte frister — og foerste kall smalt.
* NY TEST test_oppgaver_over_tid_taaler_oppgave_MED_frist OPPRETTER oppgaver med frist (passert / om 3 dager / om 60), saa kodeveien tvinges gjennom uansett hvordan basen ser ut. Sjekker ogsaa at statusen blir riktig (krit/folg/rute) og at frist returneres som ren dato uten klokkeslett.
* LAERDOM: en test som bare LESER eksisterende data kan ikke bevise fravaer av data-betingede krasj. Den maa opprette tilstanden den skal verne mot.

19.0.1.18.2 — TESTFIKS: oektnummer-vernet fanget en DATO:

* test_ai_arbeid_lekker_aldri_oktnummer feilet paa «urort siden 09.07.2026» — moensteret to-siffer-punktum-to-siffer treffer baade «01.02» og «09.07».
* En test som sperrer enhver dato i en beskrivelse er ubrukelig, og verre: den ville tvunget neste oekt til aa fjerne den, og dermed mistet vernet helt.
* Krever naa KONTEKST som faktisk peker paa en oekt: parentes rundt «(00.03)», «(V0.03)», eller et oektord foran «oekt 01.02», «GUI Prosjekt 06.74». En bar dato slipper gjennom — den er ikke bokfoering.
* Verifisert mot 7 skal-fanges og 7 skal-slippe foer push.

19.0.1.18.1 — HASTEFIKS: felte fiqas Staging (bygg 35155117):

* ParseError i industry_fsm/report/project_report_views.xml:73 — «Field fiq_wbs_number does not exist in model report.project.task.user.fsm». Registeret falt paa modul 508 av 648. CRITICAL: Failed to initialize database.
* ROTAARSAK: soekevisningen arvet project.view_task_search_form_base. Odoo kopierer arch-en nedover, og kjeden ender i en Enterprise-RAPPORTMODELL: _base -> view_task_search_form_project_fsm_base -> industry_fsm.project_task_view search_fsm_base -> report_project_task_user_fsm_view_search (report.project.task.user.fsm). Verifisert i basen: feltet finnes paa project.task (1 rad), ikke paa rapporten (0).
* FIKS: arver project.view_task_search_form i stedet. Verifisert i kilden at den er paa project.task, kun brukes som search_view_id, og IKKE arves videre av noen.
* De to andre arvene (liste + skjema) er kontrollert i samme runde: alle arvinger av view_task_form2 er paa project.task, og liste-visningen arves ikke av noen. Trygge.
* NY FEILKLASSE: et felt lagt i en DELT Odoo-visning arves av modeller du ikke kjenner. Modulen kan vaere feilfri isolert og likevel rive ned hele basen. Fanges IKKE av testflagget paa egen modul — krever full lasting av alle 648 moduler.

19.0.1.18.0 — FLATEN BYGGET: 3 VISNINGER x 2 AKSER (fasit utkast03):

* Fasit: docs/mockups/0.00 IQ prosjektoversikt_utkast03.html (artifact 87871eef), kartlagt ved aa AAPNE den i nettleser og KLIKKE alle 122 kontroller. Full kravspek: docs/0.00 IQ prj_flate_kravspek_KOMPLETT.md
* TRE VISNINGER: Gantt · Liste · Kanban — alle tegner SAMME datasett, saa klienten bytter visning uten ny spoerring (som fasitens renderGantt/renderListe/renderKanban).
* TO AKSER: Uke (7 kolonner) · Maaned (6 kolonner a 4 uker). Maaned bytter ALDRI visningstype. Tidsnav ‹ › + «I dag» flytter EEN kolonne.
* FEM NOEKKELTALL, alle klikkbare: I rute · Foelg opp · Kritisk · Frister denne uka · Gjort av AI. Klikk driller til Liste gruppert paa status — tall som ikke kan klikkes er en blindvei.
* GRUPPERING: prosjekt · rolle · ansvarlig · status · firma. Rollup per gruppe: verste status vinner, ellers drukner een kritisk oppgave i et prosjekt som ser fint ut paa toppnivaa.
* KOLLAPS PAA TO NIVAAER med bevisst ulik logikk: «Slaa sammen alle»/«Utvid alle» (eksplisitte) + veksling per gruppe (viser tilstanden der du staar). Nøkles paa ID, aldri navn.
* TO FARGEAKSER holdt adskilt: TID (i rute/foelg opp/kritisk) og KOST (innenfor/ over/ferdig). En oppgave kan vaere i rute paa tid og samtidig sprenge budsjettet.
* Nytt datalag get_oppgaver_over_tid() — firma-scope FOERST, henter kun oppgaver som beroerer tidsvinduet, sier aerlig fra naar listen er avkortet.
* FELLER VERIFISERT FRAVAERENDE: ingen min(px,vw) i SCSS · ingen && i t-if · ingen if() i inline t-on · ingen dobbel bindestrek i XML-kommentar · alle 20 t-on- handlere finnes som metoder i JS (maskinelt kryssjekket).

19.0.1.17.0 — AI-ARBEID SOM PROSJEKT, IKKE OEKTNUMMER (Gjermund-direktiv 20.07.2026):

* Ordrett: «Kan jeg ikke bruke prosjekter og saa kan claude gjoere hva det vil?» · «pktsystemet til Claude kan dra et vist moerk plass» · «det har kostet dager med ekstra arbide og over 100 timer».
* PROBLEMET: oektnummeret («01.02») er Claudes bokfoering, men Gjermund tvinges til aa forholde seg til det. Verre: nummeret FLYTTER SEG mens arbeidet staar stille — en referanse skrevet i dag peker paa en doed oekt i morgen. Oektnummeret ER en id; vi har bare ikke behandlet den som en.
* NY METODE get_ai_arbeid() — viser AI-sporene som ARBEID: «Kontrollrom», «Salg», «Kommunikasjon» med fremdrift. Hvilken oekt som utfoerer ser han ALDRI.
* ARBEIDSDELING (avtalt m/ AI KR 00.04, 20.07): de eier fiq.ai.spor + feltet project_id paa den (deres 19.0.2.10.0); vi eier flaten som viser det. Ingen ny datamodell — project.project overlever allerede at utfoereren byttes.
* TAALER at fiq_gui_ai_kr mangler: env.get() + AttributeError-fallback. En flate skal aldri ta ned en annen flate.
* UKOBLEDE SPOR SIES AERLIG (koblet: false) — aa skjule dem ville gitt et bilde som ser komplett ut mens noe mangler. Samme prinsipp som «1 uten samtykke skjult».
* 4 NYE TESTER, hvorav en sperrer regresjon: test_ai_arbeid_lekker_aldri_oktnummer soeker etter to-siffer-punktum-to-siffer i alt som vises. Legger noen inn oektnummer «bare som info» senere, feiler bygget.

19.0.1.16.0 — SJEKKLISTER PÅ HVA SOM HELST + MALER (Gjermund 19.07.2026):

* «både sjekkliste og steg for steg forklaringer skal være redigerbare og kunne opprettes på oppgaver, helst også på prosjekter og på HD og Feltservice og Salgsmuligheter osv. denne funksjonen kan være på det meste.»
* GENERISK KOBLING res_model + res_id (Odoos eget mønster fra ir.attachment / mail.activity). Hardkodede felt per modell (task_id, helpdesk_ticket_id, lead_id …) ville krevd endring i motoren for HVER ny modul — teknisk gjeld fra dag én. Nå kobles en ny modul på uten en eneste kodelinje her.
* fiq.sjekkliste.mixin — en modell får sjekklister med ÉN linje: _inherit = ["helpdesk.ticket", "fiq.sjekkliste.mixin"] Gir fiq_sjekkliste_ids, fremdrift, antall + apne_sjekkliste_flate().
* PROSJEKT koblet på nå (fane «Sjekklister» på project.project). HD/feltservice/salg kobles på når modulene er der — motoren er allerede klar.
* 🔴 task_id BEHOLDT som computed+store, ikke fjernet: get_wbs_tre() leser task.fiq_sjekkliste_ids per node (00.03, 19.07). Ryker task_id, ryker WBS-treet. Speiling går BEGGE veier (create/write) så Odoos egne visninger virker uendret.
* MALER: er_mal + kopier_til(res_model, res_id). «FDV — produktdokumentasjon» skrives ÉN gang og kopieres til 50 leiligheter; kopien redigeres fritt uten å røre malen. Kvitteringer følger ALDRI med en kopi — å arve andres signatur er utelukket.
* Migrering 19.0.1.16.0/post-migrate.py fyller res_model/res_id på eksisterende rader (SQL, ikke ORM — computen går motsatt vei). Idempotent.

19.0.1.15.0 — WBS-TRE MED TIMER MOT BUDSJETT (kravspek batch 15):

* TO FEIL RETTET FRA 1.14.0. (1) FLATEN VAR EN LISTEVISNING: tabell over prosjekter -> tabell over oppgaver. Gjermund: «du har kun knapt gjenskapt listevisning fra Odoo NATIVE!!!» Odoo HAR allerede prosjekter i liste — flaten ga ingen ny verdi.
* (2) FREMDRIFT BLE KAPPET PÅ 100 %. min(100.0, (ført/est)*100) viste 215,9 timer mot budsjett 10 som «100 % grønn» — et skjult 22x overforbruk. Å skjule nettopp det varselet den som styrer økonomien må se, er ikke en visningsfeil. Testen test_fremdrift_er_alltid_mellom_0_og_100 SEMENTERTE feilen; den er erstattet av tester som ville FEILET kappingen.
* NÅ: foldbart WBS-tre Blokk -> Fase -> Leilighet -> Aktivitet, bygget rekursivt fra Odoos EGET project.task-hierarki (parent_id). Ingen ny struktur oppfunnet.
* Per node: effektive timer / budsjett + fremdriftsbar. Rollup nedenfra — forelderens timer = egne + barnas (Odoo tillater timer på forelder med barn).
* FARGEAKSE (batch 15, linje 198-199) — KOST/timer, ikke frist: blå = innenfor budsjett · RØD = OVER budsjett · grønn = ferdig · grå = ikke startet. Verste status vinner oppover: ett rødt barn gjør forelderen rød, ellers drukner et overforbrukt rom i et prosjekt som «ser fint ut». Over budsjett slår ut SELV OM noden er ferdig — en ferdig aktivitet som brukte 3x budsjettet er ikke en suksess å farge grønn.
* Stripa klippes visuelt i SCSS (width kan ikke være 2159 %), men TALLET og STATUSEN er alltid ærlige. Overforbruk sies dessuten med ord: «+205,9 t over».
* Firma-bokser øverst (batch 15): konsern-total + ett valg per firma.
* Visuelt språk hentet fra fasit-mockupen prosjektoversikt_utkast02.html (V00.04): samme token-sett, mono-tall med tabular-nums, «X / Y»-mønster, mørk modus.
* SCSS-fellen min(px,vw) (dreper HELE assets-bundelen) unngått bevisst.

19.0.1.4.1 (06.74) — BYGGEFIKS: expand=/string= på <group> i søkevisning er

Odoo 18-syntaks og gjør visningen ugyldig i 19 -> rødt bygg. Fanget og rettet av
06.74 mens denne økta bygget videre. Inkludert her.

19.0.1.9.0 — OWL SJEKKLISTE-FLATE (bygg / kvitter):

* Client action fiq_sjekkliste_flate — «penere inngang» til de SAMME dataene. KANON Odoo-native først: modellen + native views virker uendret uten flaten.
* TO MODUSER i ÉN komponent (Gjermund: «PC-eier legger til / mobil-arbeider kvitterer»): - bygg    — legg til punkter, veksle krav 📄 dok / 📷 foto / ✍ signatur, slett punkt - kvitter — stor hake (hanske/byggeplass), last opp foto/dok, signér Modus defaulter fra user.isInternalUser, men er togglebar (byggeleder på mobil).
* Opplasting via KJERNENS FileInput -> /web/binary/upload_attachment med resModel/resId -> ir.attachment knyttes til punktet, id skrives i kvitt_foto_id/ kvitt_dok_id. Ingen egen base64-håndtering (verifisert mot web/core/file_input).
* Krav-constraint RESPEKTERES: kan et punkt ikke kvitteres, er haken sperret og «Venter på: dokument + foto» vises. Feiler et forsøk, vises modellens ValidationError som varsel — flaten feiler ALDRI stille.
* Inngangsdører: eget menypunkt · knapp i sjekkliste-skjemaets header (apne_flate) · knapp på oppgavens sjekkliste-fane (apne_sjekkliste_flate, filtrerer på oppgaven).
* RETTIGHETSNØYTRAL: ingen ny res.groups. Arver security fra ir.model.access.csv (intern = CRUD, portal = les liste + skriv punkt). Rolle-motoren eier tilgang.
* Verifisert mot Odoo 19-kilde på Staging: useService fra @web/core/utils/hooks, user.isInternalUser/name, luxon global, and i t-if (575 treff i core vs 42 &&). SCSS uten min(px,vw) (den fellen dreper hele assets-bundelen).

19.0.1.5.0 — NATIVE MENYPUNKT (flaten var UÅPNELIG):

* Modulen hadde INGEN menypunkter, og KR-skallet lenket ikke til flaten (grep: 0 treff) -> «FIQ Prosjekt» var registrert som klient-handling, men uten dør inn.
* Nå: toppmeny «FIQ Prosjekt» → «Prosjektoversikt» (flaten) + «Sjekklister».
* AI PK-avgjørelse 2026-07-17: hver flate-eier legger EGET native menypunkt. «Er KR et LAG, kan det ikke være eneste dør inn — da blir KR et single-point-of-failure for tilgjengelighet.» KR-sidemenyen kommer i TILLEGG (06.74), ikke som forutsetning.
* web_icon låner Odoos eget project-ikon (modulen har ingen egen icon.png — verifisert).

19.0.1.4.0 — GENERISK SJEKKLISTE-MOTOR:

* fiq.sjekkliste + fiq.sjekkliste.punkt — ÉN motor, ulik mottaker/flate. NIVÅ: firma · prosjekt · fase/port · oppgave · rom/objekt · leveranse (UE). TYPE: arbeid · KS · våtrom · SHA · FDV · klima · avvik · endring.
* KRAV er UAVHENGIGE (Gjermund 16.07.2026): dok / foto / signatur. FDV og klima ER dokumenter — ikke bilder. Kun avvik/endring er bilde og/eller dokument.
* Punkt kan ikke kvitteres ut før ALLE krav er levert (constraint + mangler-felt).
* Punkt-tittel/beskrivelse er translate=True — ellers får den polske snekkeren norsk (samme feil som Vidir 2382: engelsk sjargong -> 0 dokumenter levert).
* ISO 9001: versjon bumpes ved hver endring.
* Portal-tilgang: arbeider/UE kan kvittere uten Odoo-lisens (kvitt_av = Char).
* Fane «Sjekklister» på oppgaven + egen liste/skjema/søk med gruppering.
* ANTI-FORVEKSLING: dette er IKKE fiq_project_checklist (KS/våtrom = eget spor).

19.0.1.3.0:

* NYTT native felt fiq_wbs_number på project.task — dynamisk disposisjonsnummer (01, 01.02). Rekalkuleres ved flytting i treet; store+indeksert.
* Synlig i Odoos EGNE views: liste (optional=show), skjema, søk/gruppering.
* Nummer-modellen respektert: code (oppgavenr.) og sequence_code (prosjektnr.) er STABILE og røres aldri — kun WBS er dynamisk.

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
