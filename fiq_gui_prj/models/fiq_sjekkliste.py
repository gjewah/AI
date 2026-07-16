# -*- coding: utf-8 -*-
"""FIQ Sjekkliste — generisk motor (core).

Gjermund 2026-07-16: «Jeg sier IKKE et NEI til sjekklister, MEN JA. Det er bare snakk om
på hvilke NIVÅ og hvilke TYPER. Funksjonen må være der GENERISK.»

KJERNEN — færre oppgaver: punktene ER stegene. 71 oppgaver (Vidir 2382) = 9 sjekklister à ~7 punkter.
Oppgavebeskrivelsene der sa det selv: «The Checklists — Is done for Stages…» — de prøvde å lage
sjekklister, men hadde bare oppgaver som verktøy.

ÉN MOTOR — ulik mottaker/flate:
  Admin-nøkkel  -> Gjermund     -> AI KR «Krever deg»
  FDV-leveranse -> UE Maler     -> portal/mobil
  Timer+SHA     -> utearbeider  -> drift.sdvp.no

KRAV-TYPER (Gjermund 16.07.2026) — UAVHENGIGE, ikke enten/eller:
  dok  = DOKUMENT  — FDV og klima ER dokumenter, ikke bilder
  foto = BILDE     — kun der noe skal OBSERVERES: avvik og endringer
  sign = SIGNATUR  — bekreftelse/overlevering
«Det er kun avvik og endringer som er bilder og/eller dokumenter.»

ANTI-KS-FORVEKSLING: dette er IKKE fiq_project_checklist (KS/våtrom = eget kvalitetskontroll-spor).
KK-INTEGRASJON: KKs API dekker KUN stamdata — ingen sjekkliste-/avviks-endepunkt (verifisert mot
leverandørens dok). Eksport mot KK = fil, ikke API. SSOT er SINGLE: Odoo er sannheten.
"""

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class FiqSjekkliste(models.Model):
    _name = "fiq.sjekkliste"
    _description = "FIQ Sjekkliste"
    _order = "id desc"

    name = fields.Char(string="Navn", required=True, translate=True)
    # NIVÅ — hvor lista henger (Gjermunds «på hvilke nivå»)
    nivaa = fields.Selection(
        [
            ("firma", "Firma"),
            ("prosjekt", "Prosjekt"),
            ("fase", "Fase / port"),
            ("oppgave", "Oppgave"),
            ("rom", "Rom / objekt"),
            ("leveranse", "Leveranse (UE)"),
        ],
        string="Nivå", default="oppgave", required=True,
        help="Hvor sjekklista henger. Oppgave-nivå er kjernen — der «færre oppgaver» realiseres.",
    )
    # TYPE — hva slags liste (Gjermunds «hvilke typer»)
    type_liste = fields.Selection(
        [
            ("arbeid", "Arbeids-/stegliste"),
            ("ks", "KS / kvalitetskontroll"),
            ("vatrom", "Våtrom (Våtromsnormen)"),
            ("sha", "SHA / HMS"),
            ("fdv", "FDV — dokumentkrav"),
            ("klima", "Klimadokumentasjon"),
            ("avvik", "Avvik"),
            ("endring", "Endring"),
        ],
        string="Type", default="arbeid", required=True,
    )
    task_id = fields.Many2one("project.task", string="Oppgave", ondelete="cascade", index=True)
    project_id = fields.Many2one("project.project", string="Prosjekt", index=True)
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True,
        default=lambda self: self.env.company,
        help="Tenant-isolert. Scope hentes fra sesjonen — aldri fra klient.",
    )
    versjon = fields.Char(string="Versjon", default="1.0", readonly=True,
                          help="ISO 9001: bumpes ved hver endring. Kan rulles tilbake.")
    punkt_ids = fields.One2many("fiq.sjekkliste.punkt", "sjekkliste_id", string="Punkter")

    antall_punkt = fields.Integer(compute="_compute_fremdrift", store=True)
    antall_ok = fields.Integer(compute="_compute_fremdrift", store=True)
    # NB: Odoo 19 bruker `aggregator=` — `group_operator=` er utgått (verifisert mot
    # addons/project/models/project_task.py i levende 19-installasjon 2026-07-16).
    fremdrift = fields.Float(string="Utført (%)", compute="_compute_fremdrift", store=True,
                             aggregator="avg")

    @api.depends("punkt_ids", "punkt_ids.utfoert")
    def _compute_fremdrift(self):
        for s in self:
            tot = len(s.punkt_ids)
            ok = len(s.punkt_ids.filtered("utfoert"))
            s.antall_punkt = tot
            s.antall_ok = ok
            s.fremdrift = (ok / tot * 100.0) if tot else 0.0

    def _bump_versjon(self):
        """ISO 9001: hver endring gir ny versjon (1.0 -> 1.1)."""
        for s in self:
            try:
                s.versjon = "%.1f" % (float(s.versjon or "1.0") + 0.1)
            except (ValueError, TypeError):
                s.versjon = "1.0"


class FiqSjekklistePunkt(models.Model):
    _name = "fiq.sjekkliste.punkt"
    _description = "FIQ Sjekkliste-punkt"
    _order = "sequence, id"

    sjekkliste_id = fields.Many2one("fiq.sjekkliste", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    # Flerspråk: punktene MÅ være oversettbare — ellers får den polske snekkeren norsk.
    # Samme feil som Vidir 2382: engelsk sjargong til norske eksterne -> 0 dokumenter levert.
    name = fields.Char(string="Punkt", required=True, translate=True)
    beskrivelse = fields.Text(string="Hva forventes", translate=True)

    # KRAV — uavhengige (Gjermund: «signatur OG/eller foto»; FDV/klima = dokument)
    krav_dok = fields.Boolean(string="Krever dokument")
    krav_foto = fields.Boolean(string="Krever foto")
    krav_sign = fields.Boolean(string="Krever signatur")

    # KVITTERING
    utfoert = fields.Boolean(string="Utført")
    kvitt_dok_id = fields.Many2one("ir.attachment", string="Dokument")
    kvitt_foto_id = fields.Many2one("ir.attachment", string="Foto")
    kvitt_sign_av = fields.Char(string="Signert av")
    kvitt_sign_dato = fields.Datetime(string="Signert")
    kvitt_av = fields.Char(string="Kvittert av",
                           help="Kan være arbeider uten Odoo-lisens (portal) — derfor Char, ikke res.users.")
    kvitt_dato = fields.Datetime(string="Kvittert")

    kan_kvitteres = fields.Boolean(compute="_compute_kan_kvitteres",
                                   help="Alle krav innfridd? Punktet kan ikke lukkes før.")
    mangler = fields.Char(compute="_compute_kan_kvitteres", string="Venter på")

    @api.depends("krav_dok", "krav_foto", "krav_sign",
                 "kvitt_dok_id", "kvitt_foto_id", "kvitt_sign_dato")
    def _compute_kan_kvitteres(self):
        for p in self:
            m = []
            if p.krav_dok and not p.kvitt_dok_id:
                m.append("dokument")
            if p.krav_foto and not p.kvitt_foto_id:
                m.append("foto")
            if p.krav_sign and not p.kvitt_sign_dato:
                m.append("signatur")
            p.mangler = " + ".join(m) if m else False
            p.kan_kvitteres = not m

    @api.constrains("utfoert")
    def _sjekk_krav_for_utfoert(self):
        """Et punkt kan ikke merkes utført før ALLE krav er levert."""
        for p in self:
            if p.utfoert and not p.kan_kvitteres:
                raise ValidationError(
                    "«%s» kan ikke kvitteres ut — venter %s." % (p.name, p.mangler)
                )

    def write(self, vals):
        res = super().write(vals)
        # ISO 9001: enhver endring bumper listas versjon
        if {"utfoert", "krav_dok", "krav_foto", "krav_sign", "name", "beskrivelse"} & set(vals):
            self.mapped("sjekkliste_id")._bump_versjon()
        return res
