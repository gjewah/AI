#
# FIQ GUI Gantt — utvidelse av project.task.
#
# To UAVHENGIGE nummer på oppgaven (jf. dashboard_kontrollrom_spec §6):
#   * code (FIQ, FINNES via project_sequence_number) = stabil Task No. (T0001) — RØRES ALDRI.
#   * wbs_number (NYTT her) = dynamisk disposisjonsnummer (01, 01.01) som ENDRES ved flytting.
# I tillegg en ren VISNINGS-status for tid (time_status) brukt til Gantt-pilledekorasjon.
#
# Add-only: vi bygger kun oppå eksisterende felt (verifisert mot kjørende Odoo 19).
# Multicompany/tenant-isolasjon arves fra project.task sine native firma-record-rules.

from collections import defaultdict

from odoo import api, fields, models

# Felt som — når de endres — skal utløse full rekalkulering av disposisjonstreet.
_WBS_TRIGGER_FIELDS = {"sequence", "parent_id", "project_id"}


class ProjectTask(models.Model):
    _inherit = "project.task"

    # --- Disposisjonsnummer (WBS) -------------------------------------------------
    wbs_number = fields.Char(
        string="Disposisjonsnr",
        readonly=True,
        copy=False,
        index=True,
        help="Dynamisk disposisjonsnummer i MS-Project-stil (01, 01.01, 01.01.01) "
        "utledet av rekkefølge (sequence) og oppgavehierarki (parent_id) innen "
        "prosjektet. ENDRES automatisk når oppgaver flyttes/omorganiseres. "
        "Kommer i TILLEGG til den stabile FIQ-koden (Task No.).",
    )

    # --- Tids-status (kun visning, alltid ferskt → ikke lagret) -------------------
    time_status = fields.Selection(
        selection=[
            ("gronn", "I rute"),
            ("oransje", "Bak skjema"),
            ("rod", "Forfalt"),
        ],
        string="Tidsstatus",
        compute="_compute_time_status",
        store=False,
        help="🟢 i rute · 🟠 bak skjema · 🔴 forfalt. Beregnet av frist, planlagt "
        "start og fremdrift mot dagens dato. Brukes til fargedekorasjon i Gantt.",
    )

    # =====================================================================
    #  Tids-status
    # =====================================================================
    @api.depends(
        "date_deadline", "planned_date_begin", "progress", "is_closed", "state"
    )
    def _compute_time_status(self):
        """Utled en enkel, faktabasert tids-status.

        Regler (i rekkefølge):
          * Lukket/ferdig oppgave                          → 🟢 i rute
          * Frist passert og ikke ferdig                   → 🔴 forfalt
          * Frist er i dag                                 → 🟠 bak skjema
          * Innenfor planlagt vindu, men fremdriften er
            lavere enn forventet ut fra forløpt tid        → 🟠 bak skjema
          * Ellers                                         → 🟢 i rute
        """
        now = fields.Datetime.now()
        today = fields.Date.context_today(self)
        for task in self:
            status = "gronn"
            if task.is_closed:
                task.time_status = "gronn"
                continue
            deadline = task.date_deadline
            begin = task.planned_date_begin
            if deadline and deadline < now:
                status = "rod"
            elif deadline and fields.Date.to_date(deadline) == today:
                status = "oransje"
            elif begin and deadline and begin <= now <= deadline:
                total = (deadline - begin).total_seconds()
                if total > 0:
                    forventet = (now - begin).total_seconds() / total  # 0..1
                    # 🔴 progress fra hr_timesheet er en ANDEL (0..1), IKKE prosent:
                    #   progress = round((effective + subtask_effective) / allocated, 2)
                    #   (hr_timesheet/models/project_task.py:100)
                    # Verifisert mot ekte data paa Dev 23.07: 50 timer brukt av 15
                    # allokerte gir progress = 3.33 — ikke 333. Aa dele paa 100 her
                    # gjorde en 100 %-ferdig oppgave til «1 % gjort», slik at ALT
                    # ble flagget «bak skjema» saa snart ~16 % av vinduet var gaatt.
                    faktisk = task.progress or 0.0
                    # 15 %-poeng margin før vi flagger «bak skjema».
                    if faktisk + 0.15 < forventet:
                        status = "oransje"
            task.time_status = status

    # =====================================================================
    #  Disposisjonsnummer (WBS) — rekalkuleres for hele prosjekt-treet
    # =====================================================================
    def _fiq_recompute_wbs(self, projects):
        """Rekalkuler wbs_number for ALLE oppgaver i de gitte prosjektene.

        Bygger søsken-grupper (per forelder innen prosjektet), sorterer på
        (sequence, id) og tildeler nummer rekursivt: rot = 01/02…, barn =
        01.01/01.02… Skriver kun der verdien faktisk endrer seg.
        """
        Task = self.env["project.task"].sudo().with_context(active_test=False)
        projects = projects.exists()
        for project in projects:
            tasks = Task.search([("project_id", "=", project.id)])
            if not tasks:
                continue
            task_ids = set(tasks.ids)
            by_parent = defaultdict(list)
            for t in tasks:
                # Forelder teller kun som forelder hvis den er i SAMME prosjekt.
                pid = t.parent_id.id if t.parent_id.id in task_ids else False
                by_parent[pid].append(t)
            for group in by_parent.values():
                group.sort(key=lambda t: (t.sequence, t.id))

            new_values = {}

            # B023: `by_parent` og `new_values` bindes EKSPLISITT som standardverdier.
            # Koden var korrekt slik den sto — `_walk` kalles i samme løkkerunde som den
            # defineres, så den ser alltid riktig prosjekt. Men bindingen var implisitt:
            # flyttet noen kallet ut av løkka (eller la det i en liste for senere kjøring),
            # ville ALLE prosjekter fått siste prosjekts data — uten feilmelding, bare gale
            # WBS-numre. Eksplisitt binding gjør riktig oppførsel til noe koden garanterer,
            # ikke noe den tilfeldigvis får til.
            def _walk(parent_id, prefix, _bp=by_parent, _nv=new_values):
                for idx, t in enumerate(_bp.get(parent_id, []), start=1):
                    number = f"{prefix}{idx:02d}"
                    _nv[t.id] = number
                    _walk(t.id, number + ".", _bp, _nv)

            _walk(False, "")

            # Grupper oppgaver per ny verdi → færre skrivinger. Kun endringer.
            to_write = defaultdict(list)
            for t in tasks:
                target = new_values.get(t.id, False)
                if t.wbs_number != target:
                    to_write[target].append(t.id)
            for value, ids in to_write.items():
                # Skriver kun wbs_number → utløser IKKE en ny WBS-rekalkulering
                # (wbs_number er ikke blant _WBS_TRIGGER_FIELDS).
                Task.browse(ids).write({"wbs_number": value})

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        self._fiq_recompute_wbs(tasks.mapped("project_id"))
        return tasks

    def write(self, vals):
        # Fang gamle prosjekter FØR skriving (ved flytting mellom prosjekter).
        recompute = bool(_WBS_TRIGGER_FIELDS.intersection(vals))
        old_projects = (
            self.mapped("project_id") if recompute else self.env["project.project"]
        )
        res = super().write(vals)
        if recompute:
            self._fiq_recompute_wbs(old_projects | self.mapped("project_id"))
        return res
