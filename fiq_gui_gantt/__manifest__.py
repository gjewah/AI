# -*- coding: utf-8 -*-
{
    "name": "FIQ GUI Gantt",
    "version": "19.0.1.1.0",
    "summary": "Native web_gantt for prosjekt og oppgaver + FIQ-tillegg: "
               "disposisjonsnummer (WBS), tids-status-farge (grønn/oransje/rød), "
               "drill prosjekt→oppgave og milepæl-Gantt. Generisk, multicompany, "
               "tenant-isolert — for alle FIQ AS-kunder.",
    "description": """
FIQ GUI Gantt
=============
Legger et FIQ-lag OPPÅ Odoos native Enterprise-Gantt (``web_gantt``) for
prosjekter og prosjektoppgaver — uten å erstatte native funksjonalitet.

Kjernefunksjoner (jf. dashboard_kontrollrom_spec §6):

* **Disposisjonsnummer** ``wbs_number`` (NYTT, lagret/utledet) på ``project.task``:
  dynamisk MS-Project-stil nummer (``01``, ``01.01``, ``01.01.01``) som
  rekalkuleres for HELE prosjekt-treet når ``sequence``/``parent_id``/``project_id``
  endres. Kommer I TILLEGG til FIQs stabile ``code`` (Task No., røres ALDRI) og
  ``sequence_code`` (Project No., røres ALDRI).
* **Tids-status-farge** ``time_status`` (🟢 i rute · 🟠 bak skjema · 🔴 forfalt) på
  prosjekt, oppgave og milepæl — brukt som Gantt-pilledekorasjon.
* **Gantt-views** for både ``project.project`` og ``project.task`` (native
  ``web_gantt``), med progresjon, avhengigheter og skala dag/uke/måned/år.
* **Drill-ned** prosjekt-Gantt → oppgave-Gantt (knapp i prosjektskjema).
* **Milepæl-Gantt** (delmål som endagssøyler via avledede datotider).

Multicompany: bygger kun oppå eksisterende modeller (``project.*``) som allerede
har ``company_id`` + native firma-record-rules → tenant-isolasjon og time-rollup
per firma arves. Add-only, ingen destruktiv endring.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Services/Project",
    # OPL-1: avhenger av Enterprise-moduler (web_gantt / project_enterprise).
    "license": "OPL-1",
    "depends": [
        "project",
        "project_enterprise",
        "web_gantt",
        # progress-feltet paa project.task eies av hr_timesheet; _compute_time_status
        # avhenger av det, saa modulen maa lastes foer oss (ellers: 'progress' not found).
        "hr_timesheet",
        # code (project.task) og sequence_code (project.project) eies av
        # project_sequence_number - IKKE av Odoo-kjernen. Begge brukes direkte i
        # Gantt-viewene vaare (project_task_gantt_views.xml / project_project_gantt_views.xml).
        # Uten denne depends feiler installasjonen paa en base der modulen er
        # uninstalled: «Field "code" does not exist in model "project.task"»
        # (verifisert paa Dev 23.07 - modulen lot seg ikke installere i det hele tatt).
        "project_sequence_number",
    ],
    "data": [
        "views/project_task_gantt_views.xml",
        "views/project_project_gantt_views.xml",
        "views/project_milestone_gantt_views.xml",
        "views/fiq_gui_gantt_menus.xml",
    ],
    "application": False,
    "installable": True,
}
