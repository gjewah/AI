# -*- coding: utf-8 -*-
"""FIQ Prosjekt — native felt på project.task.

KANON «Odoo-native først» (Gjermund 2026-07-16): KR er et LAG, ikke systemet.
Testen for enhver ny funksjon: «Virker dette i native Odoo uten KR?»
→ Feltene her er ekte Odoo-felt med Odoo-visning. Slås KR av, står de fortsatt.

NUMMER-MODELLEN (bland dem ALDRI — jf. dashboard_kontrollrom_spec §6):
  sequence_code  project.project  «2026-00001»  STABIL — røres aldri
  code           project.task     «T0001»       STABIL — røres aldri (fiq project_sequence_number)
  wbs_number     project.task     «01.02»       DYNAMISK — rekalkuleres ved flytting i treet
"""

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    # Sjekklister på oppgaven — punktene ER stegene (færre oppgaver).
    fiq_sjekkliste_ids = fields.One2many(
        "fiq.sjekkliste", "task_id", string="Sjekklister",
    )
    fiq_sjekkliste_fremdrift = fields.Float(
        string="Sjekkliste utført (%)",
        compute="_compute_fiq_sjekkliste_fremdrift", store=True, aggregator="avg",
        help="Snitt av sjekklistenes fremdrift. Vises i native views — virker uten KR.",
    )

    @api.depends("fiq_sjekkliste_ids.fremdrift")
    def _compute_fiq_sjekkliste_fremdrift(self):
        for t in self:
            lister = t.fiq_sjekkliste_ids
            t.fiq_sjekkliste_fremdrift = (
                sum(lister.mapped("fremdrift")) / len(lister) if lister else 0.0
            )

    # Dynamisk disposisjonsnummer (MS Project-modell): endres når oppgaven flyttes.
    # store=True så den kan sorteres/grupperes/søkes på i native views.
    fiq_wbs_number = fields.Char(
        string="Disposisjonsnr.",
        compute="_compute_fiq_wbs_number",
        store=True,
        recursive=True,
        index=True,
        help="Dynamisk WBS-nummer (01, 01.02). Rekalkuleres ved flytting i treet. "
             "Oppgavenr. (code) og prosjektnr. (sequence_code) er stabile og røres aldri.",
    )

    @api.depends("sequence", "parent_id", "parent_id.fiq_wbs_number", "project_id")
    def _compute_fiq_wbs_number(self):
        """Beregn disposisjonsnummer ut fra plassering i treet.

        Toppnivå i et prosjekt -> 01, 02, 03 ...
        Underoppgave           -> <forelders wbs>.<løpenr>
        Rekkefølgen følger native `sequence`, med id som stabil tiebreaker.

        🔴 BUGFIKS 17.07.2026 (funnet på ekte data, fiqas Staging):
        Forrige versjon brukte `list(sorted_recordset).index(task)`. Det sammenligner
        RECORD-OBJEKTER og er upålitelig — med mange søsken på samme `sequence` (Odoos
        default = 10) fant hver oppgave seg selv på plass 1. Resultat: 66 av 66 toppnivå-
        oppgaver i PeP25_059 fikk `01`. Fikset ved å slå opp posisjon via ID-liste, som
        er entydig, + batch-oppslag så vi ikke søker per oppgave.
        """
        # Batch: hent alle toppnivå-søsken for de berørte prosjektene i ETT søk,
        # i stedet for ett search() per oppgave (N+1 på store baser).
        prosjekt_ids = self.filtered(lambda t: not t.parent_id).project_id.ids
        topp_per_prosjekt = {}
        if prosjekt_ids:
            alle = self.search(
                [("project_id", "in", prosjekt_ids), ("parent_id", "=", False)],
                order="sequence, id",
            )
            for t in alle:
                topp_per_prosjekt.setdefault(t.project_id.id, []).append(t.id)

        for task in self:
            if not task.project_id and not task.parent_id:
                task.fiq_wbs_number = False
                continue

            if task.parent_id:
                # Søsken under samme forelder — sorter likt som Odoo (sequence, id)
                sok = task.parent_id.child_ids.sorted(key=lambda t: (t.sequence, t.id))
                sibs_ids = sok.ids
                prefix = task.parent_id.fiq_wbs_number or ""
            else:
                sibs_ids = topp_per_prosjekt.get(task.project_id.id, [])
                prefix = ""

            # Posisjon via ID — entydig, i motsetning til record-sammenligning
            if task.id in sibs_ids:
                pos = sibs_ids.index(task.id) + 1
            else:
                # Ny/ulagret oppgave (NewId under create) — legges bakerst
                pos = len(sibs_ids) + 1

            nr = str(pos).zfill(2)
            task.fiq_wbs_number = "%s.%s" % (prefix, nr) if prefix else nr
