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
        """
        # Grupper per «forelder-kontekst» så vi teller riktig innenfor hver gren.
        for task in self:
            if not task.project_id and not task.parent_id:
                task.fiq_wbs_number = False
                continue

            if task.parent_id:
                sibs = task.parent_id.child_ids
                prefix = task.parent_id.fiq_wbs_number or ""
            else:
                sibs = self.search([
                    ("project_id", "=", task.project_id.id),
                    ("parent_id", "=", False),
                ])
                prefix = ""

            # Sorter som Odoo selv gjør: sequence, så id (stabilt ved lik sequence)
            ordered = sibs.sorted(key=lambda t: (t.sequence, t.id))
            try:
                pos = list(ordered).index(task) + 1
            except ValueError:
                # Oppgaven er ikke (ennå) i søskenlista — f.eks. under create
                pos = len(ordered) + 1

            nr = str(pos).zfill(2)
            task.fiq_wbs_number = "%s.%s" % (prefix, nr) if prefix else nr
