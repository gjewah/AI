"""STADIENE — oppgaver flytter seg, de forsvinner ikke.

Gjermund 22.07.2026, ordrett:
  «må flyttes fra et stadie til neste eller blir jo listen helt statisk»

Fasit: artifact 72aae7c9 «FIQ AI · Kontrollrom», bygget av AI PK sammen med
Gjermund gjennom ~30 iterasjoner med hans direkte tilbakemelding.

═══ FEM STADIER — «Kvalitetssikring» er HANS eget ledd ═══
  I Kø → Venter Avklaring → I Arbeid → Kvalitetssikring → Ferdig

KS er ikke pynt: det er leddet der noen sjekker om svaret faktisk var
tilstrekkelig. Uten det går arbeid rett fra «gjort» til «ferdig» uten at
noen har sett på om det holdt.

═══ 🛑 NATIVE STADIER, IKKE EGEN TABELL ═══
Vi seeder `project.task.type` — Odoos EGNE stadier. Ingen parallell modell.
Kanon (Gjermund): «Odoo uten KR skal virke.» Lager vi vår egen stadie-tabell,
virker Kanban-visningen i Odoo ikke lenger, og vi har to sannheter om hvor en
oppgave står. Målt på DEV 35275074: 26 stadier finnes allerede i basen —
mekanismen er der, vi legger bare til våre fem.

═══ FARGENE ER GJERMUNDS EGNE VALG ═══
Rød på «Venter Avklaring» og grønn på «Ferdig» er uttrykkelig bestemt av ham.
Hvit uthevet skrift — grå tekst på farge er avvist.
"""

from typing import ClassVar

from odoo import api, fields, models


class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    # Teknisk nøkkel så flaten kan kjenne igjen stadiet uten å matche på navn.
    # Navn kan oversettes og endres av Gjermund; nøkkelen kan ikke.
    fiq_ai_kode = fields.Selection(
        [
            ("ko", "I Kø"),
            ("venter", "Venter Avklaring"),
            ("arbeid", "I Arbeid"),
            ("ks", "Kvalitetssikring"),
            ("ferdig", "Ferdig"),
        ],
        string="AI KR-stadium",
        index=True,
        help="Setter stadiet inn i AI KRs rekkefølge. Tomt = vanlig Odoo-stadium.",
    )


class FiqAiStadie(models.AbstractModel):
    """Oppslag og seeding av de fem stadiene."""

    _name = "fiq.ai.stadie"
    _description = "AI KR-stadier (seedes som native project.task.type)"

    # Rekkefølge, navn og farge — alt fra fasiten, alt Gjermunds ord.
    # Fargene brukes av flaten; hvit uthevet skrift oppå (grå er avvist).
    STADIER: ClassVar = [
        ("ko", "I Kø", 10, "#4a4560"),
        ("venter", "Venter Avklaring", 20, "#c81414"),  # Gjermunds uttrykkelige valg
        ("arbeid", "I Arbeid", 30, "#1565c0"),
        ("ks", "Kvalitetssikring", 40, "#6a3fc0"),
        ("ferdig", "Ferdig", 50, "#00a844"),  # Gjermunds uttrykkelige valg
    ]

    @api.model
    def sikre_stadier(self, project_id=False):
        """Opprett de fem stadiene hvis de mangler. Kjøres ved behov, ikke ved last.

        Idempotent: finnes koden fra før, røres den ikke. En ny kjøring skal aldri
        gi duplikater eller overskrive et navn Gjermund har endret selv.
        """
        Type = self.env["project.task.type"].sudo()
        ut = []
        for kode, navn, seq, _farge in self.STADIER:
            t = Type.search([("fiq_ai_kode", "=", kode)], limit=1)
            if not t:
                # Finnes stadiet med RIKTIG NAVN fra før (opprettet manuelt), merker
                # vi det i stedet for å lage et duplikat ved siden av.
                t = Type.search(
                    [("name", "=ilike", navn), ("fiq_ai_kode", "=", False)], limit=1
                )
                if t:
                    t.write({"fiq_ai_kode": kode})
                else:
                    t = Type.create(
                        {"name": navn, "sequence": seq, "fiq_ai_kode": kode}
                    )
            if project_id and project_id not in t.project_ids.ids:
                t.write({"project_ids": [(4, int(project_id))]})
            ut.append({"id": t.id, "kode": kode, "navn": t.name})
        return ut

    @api.model
    def stadie_liste(self):
        """De fem stadiene med farge og antall — det flaten tegner som piller."""
        Type = self.env["project.task.type"].sudo()
        Task = self.env["project.task"]
        ut = []
        for kode, navn, seq, farge in self.STADIER:
            t = Type.search([("fiq_ai_kode", "=", kode)], limit=1)
            ut.append(
                {
                    "kode": kode,
                    "navn": navn,
                    "id": t.id or False,
                    "farge": farge,
                    "sekvens": seq,
                    # Kjøres som BRUKEREN, ikke sudo: tellingen skal speile det han
                    # faktisk har innsyn i. Et tall som teller andres firmaer ville
                    # vært misvisende og et tenant-brudd i praksis.
                    "antall": Task.search_count([("stage_id", "=", t.id)]) if t else 0,
                }
            )
        return ut

    @api.model
    def flytt_til(self, task_id, kode):
        """Flytt en oppgave til et stadium. Chatteren fører historikken.

        Gjermund: «må flyttes fra et stadie til neste eller blir jo listen helt
        statisk». Dette er den flyttingen — og den skjer på Odoos eget felt, så
        Kanban og rapporter følger med av seg selv.
        """
        t = self.env["project.task"].browse(int(task_id)).exists()
        if not t:
            return {"ok": False, "feil": "Oppgaven finnes ikke."}
        t.check_access("write")
        Type = self.env["project.task.type"].sudo()
        st = Type.search([("fiq_ai_kode", "=", kode)], limit=1)
        if not st:
            self.sikre_stadier()
            st = Type.search([("fiq_ai_kode", "=", kode)], limit=1)
        if not st:
            return {"ok": False, "feil": f"Ukjent stadium: {kode}"}
        t.write({"stage_id": st.id})
        return {"ok": True, "stadium": st.name, "kode": kode}
