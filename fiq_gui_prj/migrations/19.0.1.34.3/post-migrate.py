# -*- coding: utf-8 -*-
"""Sett startverdi på fiq_prioritet ut fra Odoos eksisterende priority.

🔴 UTEN DENNE MIGRERINGEN FORSVINNER DAGENS PRIORITERINGER STILLE.
Odoo fyller et nytt `required`-felt med `default` for ALLE eksisterende rader.
Uten dette skriptet ville hver eneste oppgave i basen startet på «Normal» — også
de som er markert som viktige i Odoo i dag. Ingen feilmelding, ingen tom kolonne
å oppdage: bare en flate der alt ser like viktig ut, og en bruker som tror
prioriteringene hans er der.

📌 KARTLEGGINGEN — og hva den IKKE kan gjøre:
    Odoo priority = "1"  (Important)  →  fiq_prioritet = "h"  (Høy)
    Odoo priority = "0"  (Normal)     →  fiq_prioritet = "m"  (Normal)

🔑 «Lav» kan IKKE utledes. Odoos felt har ingen verdi som betyr lav — det er
nettopp derfor AI PK besluttet et eget felt (23.07). Alt som ikke er markert
viktig i Odoo lander derfor på «Normal», ikke på «Lav». Det er en ÆRLIG
startverdi: vi vet at oppgaven ikke er viktig-markert, vi vet ikke at den er
nedprioritert. Å gjette «lav» ville vært å presentere en antakelse som data.
👉 Lav settes av mennesker etterpå. Det er en ny opplysning, ikke en migrering.

Skrives i SQL, ikke via ORM: dette er en engangs-fylling av eksisterende rader,
og en ORM-skriving over hele project_task ville trigget hver compute og
tracking-post på tabellen — på en base med hundretusener av oppgaver er det
timer, ikke sekunder.

IDEMPOTENT: kun rader der fiq_prioritet fortsatt står på default «m» røres, og
kun de som faktisk er viktig-markert i Odoo. Kjøres skriptet to ganger, gjør
andre kjøring ingenting. En oppgave et menneske alt har satt til «Lav» eller
«Høy» skrives ALDRI over — menneskets valg vinner over en utledet startverdi.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Finnes kolonnen? Odoo har normalt lagt den til før post-migrate kjører,
    # men et avbrutt løp kan etterlate basen uten den. Da skal skriptet gå
    # stille videre i stedet for å felle hele oppgraderingen.
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'project_task' AND column_name = 'fiq_prioritet'
    """)
    if not cr.fetchone():
        _logger.warning(
            "FIQ prioritet-migrering: kolonnen fiq_prioritet finnes ikke ennå "
            "— hopper over. Startverdier settes ikke."
        )
        return

    # 🔑 `fiq_prioritet = 'm'` i WHERE er selve idempotens-vakten: den treffer
    # kun rader som står på default. Har et menneske alt valgt «h» eller «l»,
    # står raden urørt.
    cr.execute("""
        UPDATE project_task
           SET fiq_prioritet = 'h'
         WHERE priority = '1'
           AND (fiq_prioritet IS NULL OR fiq_prioritet = 'm')
    """)
    til_hoy = cr.rowcount

    # Sikkerhetsnett: skulle noen rader ha kommet gjennom uten verdi (NULL i et
    # required-felt gir ValidationError ved neste skriving på raden — en feil
    # som dukker opp hos brukeren, ikke her), settes de til default.
    cr.execute("""
        UPDATE project_task
           SET fiq_prioritet = 'm'
         WHERE fiq_prioritet IS NULL
    """)
    til_normal = cr.rowcount

    _logger.info(
        "FIQ prioritet-migrering: %s oppgaver satt til Høy (viktig-markert i Odoo), "
        "%s satt til Normal. Lav settes av mennesker — den kan ikke utledes.",
        til_hoy, til_normal,
    )
