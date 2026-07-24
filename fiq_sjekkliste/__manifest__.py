{
    "name": "FIQ Sjekkliste",
    "version": "19.0.1.0.0",
    "summary": "Generisk sjekkliste-motor: niva x type, uavhengige krav "
    "(dokument/foto/signatur), maler, portal-kvittering + OWL-flate. "
    "Kobles paa en hvilken som helst modell med EEN linje.",
    "description": """19.0.1.0.0 - SKILT UT SOM EGEN MODUL (Gjermund 24.07.2026):
* Ordrett: «ja skill den ut og gjor typene konfigurerbare».
* MOTOREN LAA I fiq_gui_prj. Den er generisk (res_model/res_id) og var ALDRI
  prosjekt-spesifikk - men den kunne bare installeres ved aa dra med seg hele
  Prosjekt-modulen. Helpdesk, feltservice og salg skulle arvet WBS-tre, Gantt og
  prioritetsfelt for aa faa en sjekkliste.
* AVHENGIGHETEN TIL project ER BEHOLDT, ikke fjernet. Modellen har harde
  Many2one til project.task (linje 101) og project.project (linje 112), og
  tilgangsrettighetene bruker project.group_project_manager. Aa kutte dem ville
  revet ned Prosjekts WBS-tre, som leser task.fiq_sjekkliste_ids per node.
  🔑 Vi skilte ut det som VAR skillbart. Aa rive ut resten for en frihet ingen
  har bedt om enda, ville vaert aa betale i dag for noe vi kanskje trenger.
* EGEN ROTMENY «Sjekklister». For utskillingen hang menypunktene under
  menu_fiq_prj_root i Prosjekt - en modul som avhenger av et menypunkt i en
  annen modul er ikke utskilt, bare flyttet.
* FILENE ER FLYTTET MED `git mv`, saa historikken foelger med. Hvem som skrev
  hva og hvorfor staar fortsatt i loggen.
* SNITTET I VISNINGSFILA: motoren (skjema/liste/sok/handlinger/flate-knapp) kom
  hit. Fanene paa project.project og project.task ble IGJEN i Prosjekt - de er
  Prosjekts BRUK av motoren, ikke motoren.
* MIGRERINGEN 19.0.1.16.0/post-migrate.py ble staaende i Prosjekt. Den fylte
  res_model/res_id paa rader laget for den generiske koblingen, og er alt kjort
  der den skulle kjore.
* IKKE GJORT ENDA: typene er fortsatt en Selection i koden. Konfigurerbare typer
  er neste steg, bevisst skilt fra denne operasjonen - gjores begge i EEN
  omgang og noe feiler, vet vi ikke hvilken av dem det var.

FIQ Sjekkliste
==============
KANON «Odoo-native foerst» (Gjermund 2026-07-16): motoren + Odoos egne visninger
virker uten KR og uten OWL-flaten. Flaten er en penere inngang til de SAMME
dataene - ikke lagringen.

SLIK KOBLER EN MODUL SEG PAA (hele jobben er en linje):

    class HelpdeskTicket(models.Model):
        _name = "helpdesk.ticket"
        _inherit = ["helpdesk.ticket", "fiq.sjekkliste.mixin"]

KRAVENE ER UAVHENGIGE (Gjermund 16.07.2026): dokument / foto / signatur.
FDV og klima ER dokumenter - ikke bilder. Kun avvik/endring er bilde og/eller
dokument. Et punkt kan ikke kvitteres ut for ALLE krav er levert.

PORTAL: arbeider/UE kan kvittere uten Odoo-lisens (kvitt_av er Char).
ISO 9001: versjon bumpes ved hver endring.
ANTI-FORVEKSLING: dette er IKKE fiq_project_checklist (KS/vaatrom = eget spor).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # `project` er en EKTE avhengighet, ikke arv: Many2one til project.task og
    # project.project i modellen, og project.group_project_manager i
    # tilgangsrettighetene. Verifisert i koden for utskillingen, ikke antatt.
    "depends": ["project"],
    "data": [
        "security/ir.model.access.csv",
        "views/fiq_sjekkliste_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen. Stil, logikk, maler - i den rekkefolgen.
            "fiq_sjekkliste/static/src/sjekkliste/sjekkliste_flate.scss",
            "fiq_sjekkliste/static/src/sjekkliste/sjekkliste_flate.js",
            "fiq_sjekkliste/static/src/sjekkliste/sjekkliste_flate.xml",
        ],
    },
    "installable": True,
}
