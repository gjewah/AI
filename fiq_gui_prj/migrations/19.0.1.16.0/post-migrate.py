# -*- coding: utf-8 -*-
"""Fyll res_model/res_id på sjekklister som ble laget før den generiske koblingen.

Rader opprettet på 19.0.1.15.0 og tidligere har kun `task_id` eller `project_id`.
Uten denne migreringen ville de blitt usynlige i den generiske visningen — de ville
fortsatt virke i Odoos egne oppgave-/prosjektvisninger (One2many på task_id står), men
falt ut av flaten og av alt som spør på res_model. Det er nøyaktig den slags halvveis
tilstand som er verre enn begge alternativene.

Skrives i SQL, ikke via ORM: computen `_compute_koblinger` går fra res_model → task_id.
Her går vi motsatt vei, på data som allerede finnes, og vil ikke at computen skal
overskrive det vi setter.

Idempotent: kun rader der res_model IS NULL røres. Kjøres den to ganger, skjer
ingenting andre gang.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # Oppgave-tilknyttede lister
    cr.execute("""
        UPDATE fiq_sjekkliste
           SET res_model = 'project.task', res_id = task_id
         WHERE res_model IS NULL AND task_id IS NOT NULL
    """)
    fra_oppgave = cr.rowcount

    # Prosjekt-tilknyttede lister (kun der oppgave ikke er satt)
    cr.execute("""
        UPDATE fiq_sjekkliste
           SET res_model = 'project.project', res_id = project_id
         WHERE res_model IS NULL AND task_id IS NULL AND project_id IS NOT NULL
    """)
    fra_prosjekt = cr.rowcount

    # Frittstående lister (verken oppgave eller prosjekt) merkes som maler — det er
    # den eneste tolkningen som gir mening: en liste uten eier er en liste til gjenbruk.
    cr.execute("""
        UPDATE fiq_sjekkliste
           SET er_mal = TRUE
         WHERE res_model IS NULL AND task_id IS NULL AND project_id IS NULL
           AND er_mal IS NOT TRUE
    """)
    til_mal = cr.rowcount

    _logger.info(
        "FIQ Sjekkliste-migrering: %s fra oppgave, %s fra prosjekt, %s merket som mal.",
        fra_oppgave, fra_prosjekt, til_mal,
    )
