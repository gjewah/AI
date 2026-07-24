"""AI PROSJEKTSPOR — økter samles under spor, ikke omvendt.

Gjermund 19.07.2026, ordrett:
  «Jeg ser ikke på dette som økter men som prosjekter og det er den tullete
   økt-opplegget til Claude som skaper kaoset.»
  «Alle økter bør klassifiseres og samles inn under respektive prosjektspor.
   De øktene som flyter over flere spor må vise dette.»

DERFOR: sporet er den varige enheten. Økter er bare arbeidsperioder inne i et spor —
de kommer og går når Claude går tom for kontekst, og det skal ikke være Gjermunds problem.

═══ VERSJONSNUMMERERING (Gjermunds modell, 19.07) ═══
  00.xx  = bygges, står IKKE i Odoo ennå
  01.00  = første gang modulen faktisk STÅR og virker i Odoo   ← automatisk detektert
  01.xx  = videre arbeid på den milepælen
  → mot godkjent ferdig prosjekt

Hovedtallet bumpes AUTOMATISK når modulen er `installed` i basen (Gjermunds valg:
«Når modulen står i Odoo»). Ingen manuell bokføring — systemet ser det selv.

═══ KRYSS-SPOR (Gjermunds valg: hovedspor + gjestespor) ═══
Hver økt har ETT hovedspor (der den hører hjemme) + gjestespor den også jobber i.
Vises som «AI KR (+ Prosjekt)». Entydig eierskap, synlig overlapp — så ingen tror
to spor eier det samme.
"""

from typing import ClassVar

from odoo import api, fields, models


class FiqAiSpor(models.Model):
    _name = "fiq.ai.spor"
    _description = (
        "AI Prosjektspor (den varige enheten — økter er arbeidsperioder i den)"
    )
    _order = "kode, id"

    # Koden til oppsamlingssporet for økter som ikke har meldt tilhørighet.
    # Egen konstant, ikke en streng strødd rundt i koden — den slås opp flere steder.
    HJEMLOS_KODE = "UTEN SPOR"

    # ── SPOR-DRIFT: kodene må normaliseres, ellers flytter kaoset seg ──────────
    # Uten dette blir «KR» / «kr» / «GUI KR» / «Kontrollrom» FIRE spor for samme
    # arbeid — og da har vi flyttet øktkaoset til sporene i stedet for å fjerne
    # det. Meldt av KR-kjernen 20.07.2026; verifisert i koden før den ble rettet.
    KODE_ALIAS: ClassVar = {
        "KR": "KR",
        "GUIKR": "KR",
        "KONTROLLROM": "KR",
        "GUIKONTROLLROM": "KR",
        "AIKR": "AI KR",
        "AIKONTROLLROM": "AI KR",
        "AIRMM": "AI KR",
        "PRJ": "PRJ",
        "PROSJEKT": "PRJ",
        "GUIPRJ": "PRJ",
        "PROSJEKTOVERSIKT": "PRJ",
        "KOMM": "KOMM",
        "KOMMUNIKASJON": "KOMM",
        "MELDINGSSENTER": "KOMM",
        "MELDINGSSENTERET": "KOMM",
        "EPOST": "KOMM",
        "REL": "REL",
        "RELASJONER": "REL",
        "RELASJON": "REL",
        "FIN": "FIN",
        "FINANS": "FIN",
        "RGS": "FIN",
        "REGNSKAP": "FIN",
        "ROLLER": "ROLLER",
        "ROLLE": "ROLLER",
        "AIROLLE": "ROLLER",
        "CRM": "CRM",
        "SALG": "CRM",
        "SA": "CRM",
        "IQ": "IQ",
        "AIPK": "IQ",
        "PK": "IQ",
    }

    name = fields.Char(
        string="Spor",
        required=True,
        index=True,
        help="F.eks. «AI Kontrollrom», «Prosjekt», «Kommunikasjon».",
    )
    kode = fields.Char(
        index=True,
        help="Kort kode brukt i øktnavn, f.eks. «AI KR», «PRJ», «KOMM».",
    )
    modul = fields.Char(
        string="Odoo-modul",
        index=True,
        help="Teknisk modulnavn sporet bygger, f.eks. fiq_gui_ai_kr. "
        "Brukes til å detektere milepælen automatisk.",
    )
    beskrivelse = fields.Text(string="Hva sporet leverer")

    # ── VERSJON ─────────────────────────────────────────────────────────────────
    versjon_hoved = fields.Integer(
        string="Milepæl",
        default=0,
        help="00 = ikke i Odoo ennå · 01 = står og virker i Odoo · videre mot ferdig.",
    )
    versjon_lop = fields.Integer(
        string="Løpenr",
        default=0,
        help="Teller opp for hver ny økt innenfor samme milepæl.",
    )
    versjon = fields.Char(
        compute="_compute_versjon",
        store=True,
        help="«00.03» — vises i øktnavnet.",
    )

    modul_installert = fields.Boolean(
        string="Står i Odoo",
        compute="_compute_modul_status",
        help="Leses fra ir.module.module. Utløser milepæl 01 første gang den er sann.",
    )
    modul_versjon = fields.Char(string="Modulversjon", compute="_compute_modul_status")

    status = fields.Selection(
        [
            ("planlagt", "Planlagt"),
            ("bygges", "Bygges"),
            ("i_odoo", "Står i Odoo"),
            ("testet", "Testet"),
            ("produksjon", "I Production"),
            ("godkjent", "Godkjent ferdig"),
        ],
        default="bygges",
        index=True,
    )

    # ── KOBLING TIL ET EKTE ODOO-PROSJEKT ───────────────────────────────────────
    # Gjermund 19.07.2026: «Kan jeg ikke bruke prosjekter og så kan claude gjøre hva det
    # vil?» — han vil se AI-arbeid som PROSJEKTER, ikke som økter. «pktsystemet til Claude
    # kan dra et vist mørk plass … det har kostet dager med ekstra arbeid og over 100 timer.»
    #
    # Sporet var den varige enheten, men lå usynlig for ham fordi ingenting knyttet det til
    # noe han faktisk åpner. Denne ene koblingen lukker hullet: sporet får et hjem i
    # prosjektlista, med fremdrift, oppgaver og historikk der han allerede jobber.
    #
    # 🛑 KANON STÅR: prosjekter opprettes ALDRI maskinelt (wizarden eier flyten). Feltet
    # PEKER på et prosjekt som allerede finnes — det oppretter aldri noe.
    project_id = fields.Many2one(
        "project.project",
        string="Prosjekt",
        index=True,
        ondelete="set null",
        help="Odoo-prosjektet dette sporet arbeider i. Sporet vises da som et prosjekt "
        "med fremdrift og oppgaver — ikke som en økt med nummer.",
    )
    project_navn = fields.Char(
        string="Prosjekt (navn)",
        related="project_id.display_name",
        readonly=True,
        help="Navn, aldri ID — jf. husets navnekonvensjon.",
    )

    okt_ids = fields.One2many("fiq.ai.okt", "spor_id", string="Økter i sporet")
    antall_okter = fields.Integer(compute="_compute_okter", store=True)
    aktive_okter = fields.Integer(compute="_compute_okter", store=True)
    company_id = fields.Many2one(
        "res.company", string="Firma", index=True, default=lambda self: self.env.company
    )

    # 🔴 ODOO 19: `_sql_constraints` er UTGÅTT — gir «Model attribute '_sql_constraints'
    # is no longer supported» og gjør bygget oransje. Riktig form er `models.Constraint`
    # som klasseattributt (verifisert mot core: addons/project/models/project_tags.py:25,
    # project_project.py:186, project_task.py:331). Skrevet fra hukommelsen første gang —
    # det er nettopp slik 18-syntaks sniker seg inn.
    _kode_unik = models.Constraint(
        "unique (kode, company_id)",
        "Sporkoden må være unik per firma.",
    )

    @api.depends("versjon_hoved", "versjon_lop")
    def _compute_versjon(self):
        for s in self:
            s.versjon = f"{s.versjon_hoved or 0:02d}.{s.versjon_lop or 0:02d}"

    @api.depends("okt_ids", "okt_ids.status")
    def _compute_okter(self):
        for s in self:
            s.antall_okter = len(s.okt_ids)
            s.aktive_okter = len(s.okt_ids.filtered(lambda o: o.status == "aktiv"))

    def _compute_modul_status(self):
        """Les faktisk tilstand fra Odoo — ikke fra en påstand i et dokument."""
        Mod = self.env["ir.module.module"].sudo()
        for s in self:
            s.modul_installert = False
            s.modul_versjon = ""
            if not s.modul:
                continue
            m = Mod.search([("name", "=", s.modul)], limit=1)
            if m:
                s.modul_installert = m.state == "installed"
                s.modul_versjon = m.latest_version or ""

    @api.model
    def sjekk_milepaeler(self):
        """Bump 00 → 01 for spor der modulen nå faktisk STÅR i Odoo.

        Gjermunds valg 19.07: hovedtallet bumpes «når modulen står i Odoo» — automatisk
        detekterbart, ingen manuell bokføring. Kjøres av cron og ved hver visning.

        Bumper KUN 00 → 01. Videre milepæler (testet/production/godkjent) er
        Gjermunds beslutning, ikke noe systemet skal gjette seg til.
        """
        bumpet = []
        for s in self.search([("versjon_hoved", "=", 0), ("modul", "!=", False)]):
            s._compute_modul_status()
            if s.modul_installert:
                s.write({"versjon_hoved": 1, "versjon_lop": 0, "status": "i_odoo"})
                bumpet.append(s.name)
        return bumpet

    @api.model
    def koble_til_prosjekter(self):
        """Koble spor til EKSISTERENDE prosjekter — oppretter aldri noe.

        Gjermund vil se AI-arbeid som prosjekter. Denne finner prosjektet som allerede
        finnes og peker sporet dit. Kjøres av cron sammen med milepæl-sjekken.

        🛑 OPPRETTER ALDRI et prosjekt. Kanon: prosjekter opprettes kun via wizarden
        (Gjermund 17.07). Finnes det ikke noe å koble til, står sporet ukoblet — og det
        er ærligere enn å lage et tomt prosjekt for å fylle et felt.
        """
        Project = self.env["project.project"].sudo()
        koblet = []
        for s in self.search([("project_id", "=", False)]):
            treff = Project.browse()
            # 1) Eksakt på sporets navn, 2) på koden. Aldri delvis-treff — «AI» ville
            #    matchet halve prosjektlista.
            for kandidat in (s.name, s.kode):
                if not kandidat:
                    continue
                treff = Project.search([("name", "=ilike", kandidat)], limit=1)
                if treff:
                    break
            if treff:
                s.project_id = treff.id
                koblet.append(f"{s.kode or s.name} -> {treff.display_name}")
        return koblet

    @api.model
    def get_spor_som_prosjekt(self, company_id=False):
        """Sporene sett som PROSJEKTER — det PRJ-flaten viser Gjermund.

        Ingen øktnummer, ingen «01.02». Han skal se «Kontrollrom», «Salg»,
        «Kommunikasjon» — navn på arbeid, ikke tekniske løpenumre.
        Arbeidsdeling avtalt med GUI Prosjekt (V0.03) 20.07: jeg eier feltet på min
        modell, de eier flaten som viser det.
        """
        dom = [("company_id", "=", int(company_id))] if company_id else []
        out = []
        for s in self.search(dom, order="kode"):
            out.append(
                {
                    "id": s.id,
                    "navn": s.name or "",
                    "kode": s.kode or "",
                    "versjon": s.versjon or "",
                    "status": s.status or "",
                    "modul": s.modul or "",
                    "i_odoo": bool(s.modul_installert),
                    "project_id": s.project_id.id or False,
                    "prosjekt": s.project_id.display_name if s.project_id else "",
                    "aktive_okter": s.aktive_okter,
                    "beskrivelse": s.beskrivelse or "",
                }
            )
        return out

    @api.model
    def normaliser_kode(self, kode):
        """Gjør en fritekst-kode til den kanoniske sporkoden.

        «gui kr» · «Kontrollrom» · «KR» → alle blir «KR». Slår først opp i
        aliaslista (bokstaver og tall alene, store bokstaver), og faller ellers
        tilbake på ren opprydding — aldri på gjetting.
        """
        raw = (kode or "").strip()
        if not raw:
            return ""
        noekkel = "".join(c for c in raw.upper() if c.isalnum())
        if noekkel in self.KODE_ALIAS:
            return self.KODE_ALIAS[noekkel]
        return " ".join(raw.upper().split())

    @api.model
    def _finn_eller_lag(self, kode):
        """Slå opp et spor på kode — opprett det hvis det ikke finnes.

        Uten dette faller en økt utenfor bare fordi ingen har opprettet sporet på
        forhånd. Da mister vi nettopp den oversikten sporene finnes for å gi.

        Koden normaliseres FØRST, så samme arbeid alltid havner i samme spor.
        """
        kode = self.normaliser_kode(kode)
        if not kode:
            return self.browse()
        spor = self.search([("kode", "=ilike", kode)], limit=1)
        if spor:
            return spor
        return self.create({"name": kode, "kode": kode, "status": "bygges"})

    @api.model
    def hjemlost_spor(self):
        """Sporet hjemløse økter havner i — synlig, ikke skjult.

        Gjermund 20.07.2026 valgte MYKT krav: en økt uten spor skal ikke avvises
        (det ville stoppet arbeid), men den skal heller ikke forsvinne i stillhet.
        Den havner her, og flaten lyser rødt til noen rydder.

        Det var nettopp usynligheten som lot tre CRM-moduler stå eierløse i 11 dager.
        """
        spor = self.search([("kode", "=", self.HJEMLOS_KODE)], limit=1)
        if spor:
            return spor
        return self.create(
            {
                "name": "Uten spor",
                "kode": self.HJEMLOS_KODE,
                "status": "planlagt",
                "beskrivelse": "Økter som ikke har meldt hvilket spor de hører til. "
                "Skal alltid være tom — hver økt her mangler eier.",
            }
        )

    def neste_okt_navn(self):
        """Navnet neste økt i sporet skal ha — «0.00 8.50 AI KR (01.02)».

        Systemet kan forberede alt, men KAN IKKE starte økta selv: en økt som går tom
        for kontekst kan ikke opprette en ny. Det klikket er Gjermunds. Vi gjør det
        derfor så billig som mulig — navnet er klart, nummeret er tildelt.
        """
        self.ensure_one()
        neste = (self.versjon_lop or 0) + 1
        return (
            f"0.00 8.50 {self.kode or self.name} "
            f"({self.versjon_hoved or 0:02d}.{neste:02d})"
        )
