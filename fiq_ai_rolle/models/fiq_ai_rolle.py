# -*- coding: utf-8 -*-
#
# AI-organisasjonens Rolle-modell (rolle_system UTKAST 01, GODKJENT 2026-07-11).
# Samme rettighetssystem styrer AI-ansatte som mennesker. Menneske-redigerbar
# (CRUD uten kode): AI-ansvarlig oppretter/redigerer/pensjonerer roller + Rådgivere.
# Prompt SKRIVES IKKE for hånd — den komponeres automatisk fra Q&A + skill.
# Org-kartet (AI KR D6) huser denne modellen; redigerbare stillingsbetegnelser = D7.
# Tenant-isolert (company_id) + per-firma utvidbar/levende.

from odoo import api, fields, models


class FiqAiRolle(models.Model):
    _name = "fiq.ai.rolle"
    _description = "AI-rolle (Leder/Rådgiver) — AI-organisasjonen"
    _order = "omraade_kode, name"

    name = fields.Char(string="Stillingsbetegnelse", required=True, index=True,
                       help="Navn, ikke ID — f.eks. «2.90 IT-Ansvarlig».")
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True,
        help="Tomt = generisk (0.00) mal; satt = tenant-isolert per firma.")
    rolletype = fields.Selection([
        ("leder", "Leder (coworker — aktiv)"),
        ("radgiver", "Rådgiver (kunnskap — selv-oppdaterende)"),
    ], string="Rolletype", default="leder", required=True, index=True)
    omraade_kode = fields.Char(string="Områdekode", index=True,
                               help="Fagområde-kode, f.eks. 2.90, 2.91, 7, 2.80.")
    skill_ref = fields.Char(string="Skill (atferd)",
                            help="Hvilken generisk skill gir rollens atferd.")
    ansvar_maal = fields.Text(string="Ansvar / mål (stillingsbeskrivelse)")
    radgivere_ids = fields.Many2many(
        "fiq.ai.rolle", "fiq_ai_rolle_radgiver_rel", "rolle_id", "radgiver_id",
        string="Rådfører", domain="[('rolletype','=','radgiver')]",
        help="Hvilke Rådgivere denne rollen rådfører seg med.")
    kpi = fields.Char(string="KPI / måltall")
    membran_scope = fields.Char(
        string="Membran-scope",
        help="Peker til policy i biblioteket «09 Sec» — hva rollen SER (tenant-grense).")
    oppdater_kadens = fields.Char(string="Oppdaterings-kadens",
                                  help="For Rådgiver-selvoppdatering (f.eks. daglig/ukentlig).")
    ansvarlig_id = fields.Many2one("res.users", string="AI-ansvarlig (menneske)",
                                   help="Mennesket som redigerer denne rollen.")
    qa_ids = fields.One2many("fiq.ai.rolle.qa", "rolle_id", string="Spørsmål & svar")
    prompt = fields.Text(
        string="System-prompt (auto)", compute="_compute_prompt", store=True,
        help="Komponeres automatisk fra Q&A + skill + ansvar. Redigeres IKKE for hånd.")
    aktiv = fields.Boolean(string="Aktiv", default=True, index=True)

    @api.depends("name", "ansvar_maal", "skill_ref", "rolletype",
                 "qa_ids.sporsmal", "qa_ids.svar", "qa_ids.sequence")
    def _compute_prompt(self):
        """Prompten komponeres fra Q&A + skill (Gjermund 11.07: AI-ansvarlig SVARER,
        skriver ikke prompt). Endres et svar → prompten oppdateres automatisk."""
        for r in self:
            deler = []
            if r.name:
                rt = dict(self._fields["rolletype"].selection).get(r.rolletype, "")
                deler.append("Du er «%s» (%s)." % (r.name, rt))
            if r.ansvar_maal:
                deler.append("Ansvar/mål: %s" % r.ansvar_maal.strip())
            if r.skill_ref:
                deler.append("Atferd (skill): %s" % r.skill_ref.strip())
            for qa in r.qa_ids.sorted(key=lambda q: (q.sequence, q.id)):
                if qa.sporsmal and qa.svar:
                    deler.append("%s %s" % (qa.sporsmal.strip(), qa.svar.strip()))
            r.prompt = "\n".join(deler)


class FiqAiRolleQa(models.Model):
    _name = "fiq.ai.rolle.qa"
    _description = "AI-rolle Q&A — AI-ansvarlig svarer (driver prompten)"
    _order = "sequence, id"

    rolle_id = fields.Many2one("fiq.ai.rolle", string="Rolle",
                               required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(string="Rekkefølge", default=10)
    sporsmal = fields.Char(string="Spørsmål", required=True)
    svar = fields.Text(string="Svar")
