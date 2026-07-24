"""FIQ-prioritet på project.task — tre nivåer der Odoo har to.

AI PK-avgjørelse 23.07.2026 (kravspek spørsmål 4), ordrett:
    «Eget felt. Odoos binære `priority` kan ikke bære tre nivåer, og Gantt-specen
     (§7) forutsetter ▴▪▾. Å presse tre verdier inn i et boolsk felt ville krevd
     en parallell tolkning ingen andre kjenner. Bygg med `fiq_prioritet`.»

🔑 HVORFOR ET EGET FELT, OG IKKE EN OMTOLKNING AV `priority`:
Odoos `priority` på project.task er en Selection med NØYAKTIG to verdier —
`("0", "Normal")` og `("1", "Important")`. Den er ikke «en skala vi kan utvide»;
den er et stjerne-ikon i Odoos egne visninger, og andre moduler leser den som
boolsk. Hadde vi lagt en tredje verdi der, ville Odoos eget stjerne-widget fått
en verdi det ikke kan tegne, og enhver modul som gjør `if task.priority == "1"`
ville lest «lav» som «ikke viktig» — riktig svar ved en tilfeldighet, feil svar
så snart noen legger til en fjerde.

🛑 ODOOS `priority` RØRES IKKE. Vi LEGGER TIL, vi erstatter ikke. Slås denne
modulen av, står Odoos egen prioritet uendret og alle andre moduler virker som før
(KANON «Odoo-native først»).

📌 FORHOLDET MELLOM DE TO — les dette før du «rydder»:
`fiq_prioritet` og `priority` er IKKE synkronisert løpende, og det er et bevisst
valg. En toveis-synk mellom et to-verdis og et tre-verdis felt kan ikke være
tapsfri: «lav» må kartlegges til «normal» i Odoo, og skriver noen så i Odoo-feltet,
overskrives «lav» stille tilbake til «normal». Vi ville byttet et synlig skille mot
en usynlig datatap-mekanisme.
👉 Migreringen setter startverdien ÉN gang (se migrations/), deretter eier
`fiq_prioritet` sitt eget nivå.
"""

from odoo import fields, models


class ProjectTask(models.Model):
    """🔑 EGEN FIL, IKKE `project_task.py` — bevisst.

    `models/project_task.py` eies av flate-sporet (WBS-nummereringen). To agenter
    som skriver i samme fil overskriver hverandre stille — samme klasse som to spor
    på samme gren, og den feilen har kostet huset en uke.
    Odoo bryr seg ikke om hvilken fil et `_inherit` står i; begge lastes inn i
    samme modell. Filskillet er for MENNESKENE, ikke for rammeverket.
    """

    _inherit = "project.task"

    # Norske etiketter — det er DETTE Gjermund ser i Odoos egne visninger.
    # Rekkefølgen er høy → lav (ikke alfabetisk): en prioritetsliste leses
    # ovenfra, og det viktigste skal stå øverst.
    #
    # 🔑 Verdiene er `h`/`m`/`l`, ikke `0`/`1`/`2`. Flaten (prj.js:437) leser dem
    # direkte: `p === "h" ? "▴" : p === "l" ? "▾" : "▪"`. Tall ville krevd en
    # oversettelse i klienten — og en oversettelse ingen andre kjenner er nettopp
    # det AI PK avviste da han valgte eget felt.
    FIQ_PRIORITET = [
        ("h", "Høy"),
        ("m", "Normal"),
        ("l", "Lav"),
    ]

    fiq_prioritet = fields.Selection(
        FIQ_PRIORITET,
        string="Prioritet",
        default="m",
        required=True,
        index=True,
        tracking=True,
        help="FIQ-prioritet i tre nivåer: Høy ▴ · Normal ▪ · Lav ▾. "
        "Odoos egen prioritet (stjerne) er uavhengig av denne og røres ikke.",
    )

    # 🛑 INGEN COMPUTE, INGEN ONCHANGE MOT `priority`.
    # Datalaget er lese-bare (kanon). Et FELT er lov — en metode som setter det
    # ut fra Odoos felt ville vært skjult skriving, og den ville dessuten låst
    # «lav» ute for godt: `priority` har ingen verdi som betyr lav, så enhver
    # avledning ville tvunget lav → normal ved neste beregning.
    #
    # 🔑 `required=True` + `default="m"` er valgt framfor et valgfritt felt fordi
    # et tomt felt måtte tolkes ETT sted til, og «tom betyr normal» er nøyaktig den
    # parallelle tolkningen AI PK avviste. Nå har hver oppgave en ekte verdi.
