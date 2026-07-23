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
    # ── GENERISK KOBLING — sjekklista kan henge på HVA SOM HELST ────────────────
    # Gjermund 19.07.2026: «både sjekkliste og steg for steg forklaringer skal være
    # redigerbare og kunne opprettes på oppgaver, helst også på prosjekter og på HD og
    # Feltservice og Salgsmuligheter osv. denne funksjonen kan være på det meste.»
    #
    # Hardkodede felt (ett per modell: task_id, project_id, helpdesk_ticket_id,
    # fsm_id, lead_id …) blir teknisk gjeld fra dag én — hver ny modul krever endring
    # HER. Derfor Odoos eget mønster for «kan henge på hva som helst»: res_model +
    # res_id, slik `ir.attachment` og `mail.activity` gjør det. En ny modul kobler seg
    # på uten en eneste kodelinje i denne motoren.
    res_model = fields.Char(
        string="Knyttet til (modell)", index=True,
        help="Teknisk modellnavn, f.eks. project.task, helpdesk.ticket, crm.lead. "
             "Sjekklista kan henge på en hvilken som helst Odoo-post.",
    )
    res_id = fields.Many2oneReference(
        string="Knyttet til (post)", model_field="res_model", index=True,
        help="Id på posten sjekklista hører til.",
    )
    res_navn = fields.Char(string="Knyttet til", compute="_compute_res_navn",
                           help="Menneskelig navn på posten — navn, ikke ID.")

    # ── BAKOVERKOMPATIBLE HJELPEFELT ────────────────────────────────────────────
    # 🔴 IKKE bare pynt: `project_task.fiq_sjekkliste_ids` er en One2many på task_id, og
    # den er i aktiv bruk i `fiq_gui_prj_data.get_wbs_tre()` (WBS-treet leser
    # task.fiq_sjekkliste_ids + fiq_sjekkliste_fremdrift per node, meldt av 00.03
    # 19.07.2026). Ryker task_id, ryker WBS-treet samtidig.
    # Derfor: computed + STORE, slik at One2many, søk og gruppering virker som før.
    task_id = fields.Many2one(
        "project.task", string="Oppgave", ondelete="cascade", index=True,
        compute="_compute_koblinger", store=True, readonly=False,
        help="Utledet av res_model/res_id når lista henger på en oppgave. "
             "Beholdt så Odoos egne visninger og WBS-treet virker uendret.",
    )
    project_id = fields.Many2one(
        "project.project", string="Prosjekt", index=True,
        compute="_compute_koblinger", store=True, readonly=False,
        help="Settes direkte når lista henger på et prosjekt, ellers arvet fra oppgaven.",
    )
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True,
        default=lambda self: self.env.company,
        help="Tenant-isolert. Scope hentes fra sesjonen — aldri fra klient.",
    )

    # ── MAL ─────────────────────────────────────────────────────────────────────
    # «FDV — produktdokumentasjon» skrives ÉN gang og gjenbrukes på 50 leiligheter.
    # Samme mønster som 0.90-malprosjektene. Kopien redigeres fritt uten å røre malen.
    er_mal = fields.Boolean(
        string="Er mal", index=True,
        help="Maler henger ikke på en post — de kopieres til en når de skal brukes.",
    )
    mal_id = fields.Many2one(
        "fiq.sjekkliste", string="Laget fra mal", ondelete="set null", index=True,
        help="Hvilken mal denne kopien kom fra. Kopien er selvstendig og kan endres fritt.",
    )
    # 🔴 RETTET 23.07: teksten lovet «Kan rulles tilbake». Det KAN den ikke —
    # `_bump_versjon()` teller opp, men lagrer ingen forrige tilstand.
    # Meldt av GUI Prosjekt (00.03), som fant det avgjørende: dette er ikke en
    # kommentar, det er en HJELPETEKST. Den vises i Odoos grensesnitt når
    # brukeren peker på feltet. Gjermund kunne lest «Kan rulles tilbake» på
    # skjermen og lett etter en knapp som ikke finnes.
    # 🔑 En hjelpetekst som lover mer enn koden holder, blir sitert som fasit —
    # her av brukeren selv, ikke bare av neste utvikler.
    # ⏸ Ekte versjonering (historikk + tilbakerulling) er et ÅPENT spørsmål hos
    # Gjermund: «hvor mye skal denne dokumentasjonen tåle å bli utfordret?»
    # Blir den bygget, endres teksten da. Til da sier den sant.
    versjon = fields.Char(string="Versjon", default="1.0", readonly=True,
                          help="Bumpes ved hver endring (1.0 → 1.1). Forrige tilstand "
                               "lagres ikke — tallet viser AT noe er endret, ikke HVA.")
    punkt_ids = fields.One2many("fiq.sjekkliste.punkt", "sjekkliste_id", string="Punkter")

    antall_punkt = fields.Integer(compute="_compute_fremdrift", store=True)
    antall_ok = fields.Integer(compute="_compute_fremdrift", store=True)
    # NB: Odoo 19 bruker `aggregator=` — `group_operator=` er utgått (verifisert mot
    # addons/project/models/project_task.py i levende 19-installasjon 2026-07-16).
    fremdrift = fields.Float(string="Utført (%)", compute="_compute_fremdrift", store=True,
                             aggregator="avg")

    @api.depends("res_model", "res_id")
    def _compute_koblinger(self):
        """Hold task_id/project_id i synk med den generiske koblingen.

        Skrives task_id direkte (gammel kode, Odoos egne visninger, One2many-en på
        oppgaven), speiles det tilbake til res_model/res_id i `create`/`write` — se
        `_speil_til_generisk`. Begge veier virker, så ingenting brekker.
        """
        for s in self:
            if s.res_model == "project.task" and s.res_id:
                oppgave = self.env["project.task"].browse(s.res_id).exists()
                s.task_id = oppgave.id or False
                # Prosjektet arves fra oppgaven — praktisk for gruppering og filtre.
                s.project_id = oppgave.project_id.id or False
            elif s.res_model == "project.project" and s.res_id:
                s.task_id = False
                s.project_id = self.env["project.project"].browse(s.res_id).exists().id or False
            elif not s.res_model:
                # Ingen generisk kobling satt — la eksisterende verdier stå (mal, eller
                # rad opprettet før omleggingen).
                s.task_id = s.task_id
                s.project_id = s.project_id
            else:
                # Knyttet til noe annet (helpdesk, feltservice, salg …) — da finnes
                # verken oppgave eller prosjekt, og det er helt i orden.
                s.task_id = False
                s.project_id = False

    @api.depends("res_model", "res_id")
    def _compute_res_navn(self):
        """Menneskelig navn på posten lista henger på — navn, ikke ID."""
        for s in self:
            s.res_navn = False
            if not (s.res_model and s.res_id):
                continue
            if s.res_model not in self.env:
                # Modulen kan være avinstallert; da skal vi ikke krasje.
                s.res_navn = "%s/%s" % (s.res_model, s.res_id)
                continue
            post = self.env[s.res_model].browse(s.res_id).exists()
            s.res_navn = post.display_name if post else False

    def _speil_til_generisk(self, vals):
        """Skrives task_id/project_id direkte, sett den generiske koblingen tilsvarende.

        Uten dette ville en post opprettet fra Odoos egen oppgave-fane (som setter
        task_id via One2many-en) fått res_model tomt, og forsvunnet ut av den generiske
        visningen. Begge veier må virke — ellers er omleggingen en felle.
        """
        if vals.get("task_id") and not vals.get("res_model"):
            vals["res_model"] = "project.task"
            vals["res_id"] = vals["task_id"]
        elif vals.get("project_id") and not vals.get("res_model") and not vals.get("task_id"):
            vals["res_model"] = "project.project"
            vals["res_id"] = vals["project_id"]
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._speil_til_generisk(dict(v)) for v in vals_list])

    @api.depends("punkt_ids", "punkt_ids.utfoert")
    def _compute_fremdrift(self):
        for s in self:
            tot = len(s.punkt_ids)
            ok = len(s.punkt_ids.filtered("utfoert"))
            s.antall_punkt = tot
            s.antall_ok = ok
            s.fremdrift = (ok / tot * 100.0) if tot else 0.0

    def _bump_versjon(self):
        """Teller opp versjonsnummeret (1.0 -> 1.1) ved hver endring.

        🛑 Dette er en TELLER, ikke versjonering. Forrige tilstand lagres ikke,
        og ingenting kan rulles tilbake. Sto tidligere som «ISO 9001» — men
        ISO 9001 krever at man kan vise hva som gjaldt paa et gitt tidspunkt,
        og det kan vi ikke. Teksten villedet BEGGE oektene i gaar (AI KR + PRJ).
        Ekte versjonering er et aapent spoersmaal hos Gjermund.
        """
        for s in self:
            try:
                s.versjon = "%.1f" % (float(s.versjon or "1.0") + 0.1)
            except (ValueError, TypeError):
                s.versjon = "1.0"

    def write(self, vals):
        # Samme speiling som i create: settes task_id/project_id direkte (Odoos egne
        # visninger gjør det), skal den generiske koblingen følge med.
        return super().write(self._speil_til_generisk(dict(vals)))

    # ── MAL → BRUK ──────────────────────────────────────────────────────────────
    def kopier_til(self, res_model, res_id):
        """Kopier denne lista (typisk en mal) til en post — med alle punkter.

        Kopien er SELVSTENDIG: den kan redigeres, punkter legges til og fjernes, uten
        at malen endres. Det er hele poenget — «FDV — produktdokumentasjon» skrives én
        gang og brukes på 50 leiligheter, der hver leilighet kan avvike.

        Kvitteringer følger ALDRI med. En kopi starter alltid ukvittert; alt annet
        ville vært å arve andres signatur.
        """
        self.ensure_one()
        if res_model not in self.env:
            raise ValidationError("Ukjent modell «%s»." % res_model)
        if not self.env[res_model].browse(res_id).exists():
            raise ValidationError("Fant ikke posten det skal kopieres til.")

        ny = self.copy({
            "name": self.name,
            "er_mal": False,
            "mal_id": self.id if self.er_mal else (self.mal_id.id or False),
            "res_model": res_model,
            "res_id": res_id,
            "versjon": "1.0",
            "punkt_ids": False,   # punktene kopieres eksplisitt under, uten kvitteringer
        })
        for p in self.punkt_ids:
            self.env["fiq.sjekkliste.punkt"].create({
                "sjekkliste_id": ny.id,
                "sequence": p.sequence,
                "name": p.name,
                "beskrivelse": p.beskrivelse,
                "krav_dok": p.krav_dok,
                "krav_foto": p.krav_foto,
                "krav_sign": p.krav_sign,
                # utfoert/kvitt_* med vilje IKKE kopiert — se docstring.
            })
        return ny

    def apne_flate(self):
        """Åpne OWL-sjekkliste-flaten forhåndsvalgt på DENNE lista.

        Flaten er en penere inngang til de samme dataene (KANON Odoo-native først) —
        knappen finnes i skjemaets header, men lista virker uten flaten.
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "fiq_sjekkliste_flate",
            "name": self.name or "Sjekkliste",
            "context": {
                "default_sjekkliste_id": self.id,
                "default_task_id": self.task_id.id or False,
            },
        }


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
        # Enhver endring teller opp listas versjon. Se _bump_versjon:
        # dette er en teller, ikke ekte versjonering.
        if {"utfoert", "krav_dok", "krav_foto", "krav_sign", "name", "beskrivelse"} & set(vals):
            self.mapped("sjekkliste_id")._bump_versjon()
        return res
