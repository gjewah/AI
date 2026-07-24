#
# FIQ Styringssystem — ISO 9001 (add-only modul).
# Forankret i referanse_metadata_iso9001.md (dokumentert informasjon §7.5) +
# metadata_taxonomy.md (code.list.item / documents.tag som taksonomi-ryggrad).
#
# UFRAVIKELIG (Gjermund-direktiv): hver modell har company_id (default env.company)
# + globale record rules per firma (se security/fiq_mgmtsystem_rules.xml). Tenant-
# isolert, generisk for ALLE FIQ AS-kunder — aldri kunde-fork. Navn ikke ID i UI.
#
# Taksonomi-kobling er FEATURE-DETEKTERT (soft): krav bærer en taksonomi-KODE
# (code.list.item.code) + valgfritt dokumentetikett-navn, og modulen slår opp
# code.list.item / documents.tag ved KJØRETID uten hard-avhengighet — så modulen
# installerer på enhver base (også uten Documents/base_code_list).

from odoo import api, fields, models


class FiqMgmtsystemKrav(models.Model):
    """Ett krav / én klausul i et styringssystem (ISO 9001 m.fl.)."""

    _name = "fiq.mgmtsystem.krav"
    _description = "Styringssystem-krav (klausul)"
    _order = "standard, klausul, name"

    name = fields.Char(
        string="Krav",
        required=True,
        index=True,
        help="Menneskelesbar tittel — navn, ikke ID.",
    )
    klausul = fields.Char(index=True, help="Klausulnummer i standarden, f.eks. «7.5».")
    standard = fields.Selection(
        [
            ("iso9001", "ISO 9001 — Kvalitet"),
            ("iso14001", "ISO 14001 — Miljø"),
            ("iso14064", "ISO 14064 — Klimagassregnskap"),
            ("iso14067", "ISO 14067 — Karbonfotavtrykk"),
            ("iso27001", "ISO 27001 — Informasjonssikkerhet"),
            ("annet", "Annet / internt"),
        ],
        default="iso9001",
        required=True,
        index=True,
    )
    beskrivelse = fields.Text()
    company_id = fields.Many2one(
        "res.company",
        string="Firma",
        index=True,
        default=lambda s: s.env.company,
        help="Tenant-isolasjon. Tomt = generisk mal delt på tvers.",
    )
    # Taksonomi-kobling (feature-detektert — se resolve_taksonomi)
    taksonomi_kode = fields.Char(
        string="Taksonomi-kode",
        help="code.list.item.code, f.eks. «2.40.01». Kobler kravet til FIQ-taksonomien "
        "(SharePoint/Documents). Slås opp ved kjøretid — ingen hard-avhengighet.",
    )
    dokumentetikett = fields.Char(
        help="Navn på documents.tag (dokumentert informasjon). Slås opp ved kjøretid."
    )
    kontroll_ids = fields.Many2many(
        "fiq.mgmtsystem.kontroll",
        "fiq_mgmtsystem_kontroll_krav_rel",
        "krav_id",
        "kontroll_id",
        string="Kontroller",
        help="Kontrollene som dekker dette kravet.",
    )
    sjekkliste_ids = fields.One2many(
        "fiq.mgmtsystem.sjekkliste", "krav_id", string="Sjekklister"
    )
    avvik_ids = fields.One2many("fiq.mgmtsystem.avvik", "krav_id")
    kontroll_antall = fields.Integer(
        string="Antall kontroller", compute="_compute_antall"
    )
    avvik_aapne = fields.Integer(string="Åpne avvik", compute="_compute_antall")
    aktiv = fields.Boolean(default=True, index=True)

    _klausul_uniq = models.Constraint(
        "unique(standard, klausul, company_id)",
        "Klausul må være unik per standard og firma.",
    )

    @api.depends("kontroll_ids", "avvik_ids", "avvik_ids.status")
    def _compute_antall(self):
        for r in self:
            r.kontroll_antall = len(r.kontroll_ids)
            r.avvik_aapne = len(r.avvik_ids.filtered(lambda a: a.status != "lukket"))

    def resolve_taksonomi(self):
        """Soft/feature-detektert oppslag av taksonomi mot code.list.item og
        documents.tag. Returnerer dict per krav uten å kreve at modulene finnes.
        Kalles fra API/GUI — kobler krav ↔ FIQ-taksonomi ved kjøretid."""
        self.ensure_one()
        res = {"code_list_item_id": False, "documents_tag_id": False}
        cli = self.env.get("code.list.item") if "code.list.item" in self.env else False
        if cli is not False and self.taksonomi_kode:
            item = cli.search([("code", "=", self.taksonomi_kode)], limit=1)
            if item:
                res["code_list_item_id"] = item.id
        dtag = self.env.get("documents.tag") if "documents.tag" in self.env else False
        if dtag is not False and self.dokumentetikett:
            tag = dtag.search([("name", "=", self.dokumentetikett)], limit=1)
            if tag:
                res["documents_tag_id"] = tag.id
        return res

    @api.model
    def get_mgmtsystem_data(self, standard=None):
        """API for GUI/AI KR: oversikt over styringssystemet for INNLOGGET firma.
        Multi-selskap håndteres av record rules (company_ids) — ikke parameter.
        Returnerer aggregat + krav-liste (navn, ikke ID, i visningsfelt)."""
        domain = [("aktiv", "=", True)]
        if standard:
            domain.append(("standard", "=", standard))
        krav = self.search(domain)
        avvik_model = self.env["fiq.mgmtsystem.avvik"]
        aapne = avvik_model.search_count([("status", "!=", "lukket")])
        std_labels = dict(self._fields["standard"].selection)
        return {
            "antall_krav": len(krav),
            "antall_kontroller": self.env["fiq.mgmtsystem.kontroll"].search_count([]),
            "antall_sjekklister": self.env["fiq.mgmtsystem.sjekkliste"].search_count(
                []
            ),
            "aapne_avvik": aapne,
            "krav": [
                {
                    "id": k.id,
                    "navn": k.name,
                    "klausul": k.klausul or "",
                    "standard": std_labels.get(k.standard, k.standard),
                    "taksonomi_kode": k.taksonomi_kode or "",
                    "kontroller": k.kontroll_antall,
                    "aapne_avvik": k.avvik_aapne,
                }
                for k in krav
            ],
        }


class FiqMgmtsystemKontroll(models.Model):
    """En kontroll som demonstrerer at ett eller flere krav etterleves."""

    _name = "fiq.mgmtsystem.kontroll"
    _description = "Styringssystem-kontroll"
    _order = "name"

    name = fields.Char(string="Kontroll", required=True, index=True)
    kode = fields.Char(index=True)
    beskrivelse = fields.Text()
    krav_ids = fields.Many2many(
        "fiq.mgmtsystem.krav",
        "fiq_mgmtsystem_kontroll_krav_rel",
        "kontroll_id",
        "krav_id",
        string="Dekker krav",
    )
    ansvarlig_id = fields.Many2one("res.users")
    frekvens = fields.Selection(
        [
            ("kontinuerlig", "Kontinuerlig"),
            ("daglig", "Daglig"),
            ("ukentlig", "Ukentlig"),
            ("manedlig", "Månedlig"),
            ("kvartalsvis", "Kvartalsvis"),
            ("arlig", "Årlig"),
            ("ad_hoc", "Ved behov"),
        ],
        default="manedlig",
    )
    neste_dato = fields.Date(string="Neste gjennomføring")
    status = fields.Selection(
        [
            ("planlagt", "Planlagt"),
            ("aktiv", "Aktiv"),
            ("utdatert", "Utdatert"),
        ],
        default="aktiv",
        index=True,
    )
    avvik_ids = fields.One2many("fiq.mgmtsystem.avvik", "kontroll_id")
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True, default=lambda s: s.env.company
    )
    aktiv = fields.Boolean(default=True, index=True)

    _kode_uniq = models.Constraint(
        "unique(kode, company_id)",
        "Kontroll-kode må være unik per firma.",
    )


class FiqMgmtsystemSjekkliste(models.Model):
    """En sjekkliste (mal eller instans) knyttet til et krav — jf. ISO-etterlevelse."""

    _name = "fiq.mgmtsystem.sjekkliste"
    _description = "Styringssystem-sjekkliste"
    _order = "name"

    name = fields.Char(string="Sjekkliste", required=True, index=True)
    krav_id = fields.Many2one("fiq.mgmtsystem.krav", index=True, ondelete="set null")
    er_mal = fields.Boolean(
        string="Mal",
        default=False,
        help="Mal = gjenbrukbar sjekkliste-mal; ellers en konkret instans.",
    )
    punkt_ids = fields.One2many(
        "fiq.mgmtsystem.sjekkliste.punkt", "sjekkliste_id", string="Punkter"
    )
    antall_punkt = fields.Integer(compute="_compute_fremdrift", string="Antall punkter")
    antall_utfort = fields.Integer(compute="_compute_fremdrift", string="Utført")
    fremdrift = fields.Float(
        string="Fremdrift (%)",
        compute="_compute_fremdrift",
        help="Andel utførte punkter.",
    )
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True, default=lambda s: s.env.company
    )
    aktiv = fields.Boolean(default=True, index=True)

    @api.depends("punkt_ids", "punkt_ids.utfort")
    def _compute_fremdrift(self):
        for r in self:
            r.antall_punkt = len(r.punkt_ids)
            r.antall_utfort = len(r.punkt_ids.filtered("utfort"))
            r.fremdrift = (
                (100.0 * r.antall_utfort / r.antall_punkt) if r.antall_punkt else 0.0
            )


class FiqMgmtsystemSjekklistePunkt(models.Model):
    """Ett punkt i en sjekkliste. Følger Vidir-standarden:
    «<deloppgave> [oppgavenr / URL] [Ansvarlig] - utført»."""

    _name = "fiq.mgmtsystem.sjekkliste.punkt"
    _description = "Sjekklistepunkt"
    _order = "sequence, id"

    name = fields.Char(string="Punkt", required=True)
    sjekkliste_id = fields.Many2one(
        "fiq.mgmtsystem.sjekkliste", required=True, ondelete="cascade", index=True
    )
    sequence = fields.Integer(string="Rekkefølge", default=10)
    utfort = fields.Boolean(string="Utført", default=False)
    ansvarlig = fields.Char(help="Ansvarlig (tekst) per Vidir-standard.")
    oppgave_ref = fields.Char(
        string="Oppgave / URL", help="Oppgavenummer eller dyplenke til Odoo-posten."
    )
    merknad = fields.Text()
    # Tenant-isolasjon: arvet fra sjekklista (lagret så record rules kan filtrere).
    company_id = fields.Many2one(
        "res.company",
        string="Firma",
        index=True,
        store=True,
        related="sjekkliste_id.company_id",
        readonly=True,
    )


class FiqMgmtsystemAvvik(models.Model):
    """Et avvik (nonconformity) — rotårsak, tiltak, alvorlighet, status.
    Sporbar via mail.thread (ISO 9001 §7.5 dokumentert informasjon)."""

    _name = "fiq.mgmtsystem.avvik"
    _description = "Styringssystem-avvik"
    _inherit = ["mail.thread"]
    _order = "oppdaget_dato desc, id desc"

    name = fields.Char(string="Avvik", required=True, index=True, tracking=True)
    krav_id = fields.Many2one("fiq.mgmtsystem.krav", index=True, ondelete="set null")
    kontroll_id = fields.Many2one(
        "fiq.mgmtsystem.kontroll", index=True, ondelete="set null"
    )
    beskrivelse = fields.Text()
    rotarsak = fields.Text(string="Rotårsak")
    tiltak = fields.Text(string="Korrigerende tiltak")
    alvorlighet = fields.Selection(
        [
            ("lav", "Lav"),
            ("middels", "Middels"),
            ("hoy", "Høy"),
            ("kritisk", "Kritisk"),
        ],
        default="middels",
        index=True,
        tracking=True,
    )
    status = fields.Selection(
        [
            ("aapen", "Åpen"),
            ("under_tiltak", "Under tiltak"),
            ("lukket", "Lukket"),
        ],
        default="aapen",
        required=True,
        index=True,
        tracking=True,
    )
    ansvarlig_id = fields.Many2one("res.users", tracking=True)
    oppdaget_dato = fields.Date(
        string="Oppdaget", default=fields.Date.context_today, index=True
    )
    frist = fields.Date()
    lukket_dato = fields.Date(string="Lukket")
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True, default=lambda s: s.env.company
    )
    aktiv = fields.Boolean(default=True, index=True)

    def action_lukk(self):
        """Bruker-handling: lukk avviket og stemple lukket-dato."""
        self.write({"status": "lukket", "lukket_dato": fields.Date.context_today(self)})
        return True
