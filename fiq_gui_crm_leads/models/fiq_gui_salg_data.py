# -*- coding: utf-8 -*-
"""Datakilde for AI GUI Salg (6 SALG) — samleboks til Kontrollrommet.

Rolle bak, flate foran: dette er VISNINGEN av «0.00 6 AI Salg-Rådgiver».
Native-først — tallene EIES av Odoo (`crm.lead`). Ingen parallell pipeline,
ingen egne summer lagret, ingen skriving. Kun lesing og gruppering.

HVA BOKSEN SVARER PÅ (Kontrollrommet har plass til tre tall, ikke tretti):
  haster = salgsmuligheter som har gått over fristen — de taper penger i stillhet
  i_dag  = de som forfaller i dag
  totalt = åpen pipeline i det hele tatt

SKILLET MOT 2.70 FINANS (ellers blir boksene like):
  2.70 FIN = kredittrisiko på KUNDER som allerede skylder penger (fakturert).
  6 SALG   = muligheter som ennå ikke er penger. Fremtid, ikke fordring.

🛑 ÅPEN PIPELINE = verken vunnet eller tapt. Odoo 19 markerer vunnet med
   `crm.stage.is_won`, og tapt via `active = False` (leaden arkiveres). En
   `search` uten videre filter ser derfor bare de aktive — men vunne ligger
   fortsatt aktive, så de må lukes ut eksplisitt. Uten det blir «åpen pipeline»
   pyntet med hver eneste handel firmaet har vunnet.

🛑 TENANT-ISOLASJON: firma hentes fra sesjonen (`self.env.company`) via
   `with_company()` — ALDRI som rå `company_id` fra klienten. Odoo håndhever
   `ir.rule` på toppen. En bruker kan dermed ikke be om et annet firmas
   salgstall ved å manipulere kallet.

🛑 IKKE `team_id` PÅ `crm.stage`: feltet finnes ikke i Odoo 19 (verifisert mot
   basen: «Invalid field 'team_id' on 'crm.stage'»). Salgsteam ligger på leaden.
"""

from odoo import api, fields, models


class FiqGuiSalgData(models.AbstractModel):
    """Leser pipeline-bildet. AbstractModel = ingen tabell, ingen lagrede tall."""

    _name = "fiq.gui.salg.data"
    _description = "FIQ Salg — pipelinedata (lesing av crm.lead)"

    @api.model
    def _apen_domene(self, selv):
        """Salgsmuligheter i AKTIVE stadier for gjeldende firma.

        `type = opportunity` skiller muligheter fra rå leads: en lead er et
        navn på en lapp, en mulighet er noe som faktisk står i pipelinen.

        🛑 «TAPT» ER IKKE ALLTID ARKIVERT — dette felte første utgave.
        Odoo markerer vunnet med `is_won`, men har INGEN tilsvarende `is_lost`
        på stadiet: et tapt salg forventes arkivert (`active = False`).
        Målt på fiqas 20.07.2026 stemmer ikke det: stadiet «9.99 Tapt» har
        25 AKTIVE saker, og `is_won` er ikke satt på det. Uten filteret under
        telles derfor hver eneste tapte sak som åpen pipeline.

        Konsekvensen var synlig: boksen meldte «26 av 28 haster», der én sak
        var 925 dager over frist. Teknisk riktig, praktisk verdiløst — en boks
        som roper hver dag blir bakgrunnsstøy, og da har flaten sluttet å
        informere. Gjermund valgte 20.07: tell kun aktive stadier.

        Løsningen leser stadienavnet framfor å hardkode en id: stadie-id-ene
        er ulike i hvert firma, mens nummereringen (`9.99`) er FIQ-konvensjon
        på tvers ([[fiq-metadata-taxonomy]]). `is_won` fanger vunnet uansett
        hva stadiet heter — begge trengs.
        """
        return [
            ("type", "=", "opportunity"),
            ("stage_id.is_won", "=", False),
            ("stage_id", "not in", selv._avsluttede_stadier(selv).ids),
            ("company_id", "in", (False, selv.env.company.id)),
        ]

    @api.model
    def _avsluttede_stadier(self, selv):
        """Stadier som betyr «ferdig», uansett om saken er arkivert.

        Vunnet fanges av `is_won`. Tapt har ingen tilsvarende markør i Odoo,
        så det leses av nummerprefikset: FIQ-pipelinene bruker `9.99` for tapt
        i alle firmaer (verifisert på fiqas: «9.99 Lost» / «9.99 Tapt»).

        Navnet leses uten språk-context med vilje: prefikset `9.99` er likt i
        alle språklinjer, mens ordet etter er oversatt. Vi matcher på tallet.
        """
        return selv.env["crm.stage"].search([
            "|", ("is_won", "=", True), ("name", "=like", "9.99%"),
        ])

    @api.model
    def get_kr_boks(self, company_id=False):
        """Samleboks til KR-forsiden.

        Kontrakt (fiq_gui_control_config.py, get_kr_bokser):
            -> {"haster": int, "i_dag": int, "totalt": int,
                "linjer": [{"tekst": str, "res_id": int}, ...]}

        Linjene rangeres etter forventet omsetning: står det tre saker på vent,
        vil man vite hvilken som er verdt mest — ikke hvilken som er eldst.

        Kan tallet ikke regnes, returneres ingenting (ingen boks) framfor en
        boks med 0 — en tom boks ser ut som «ingenting haster», og det er en
        annen påstand enn «vi vet ikke».
        """
        selv = self.with_company(company_id) if company_id else self
        i_dag = fields.Date.context_today(selv)
        Lead = selv.env["crm.lead"]

        domene = selv._apen_domene(selv)
        totalt = Lead.search_count(domene)
        if not totalt:
            return None

        # Forfalt = frist passert. Fristen er valgfri i Odoo, så en mulighet
        # uten dato er verken forfalt eller «i dag» — den bare venter.
        forfalt = Lead.search(
            domene + [("date_deadline", "<", i_dag)],
            order="expected_revenue desc",
        )
        i_dag_ant = Lead.search_count(domene + [("date_deadline", "=", i_dag)])

        linjer = []
        for lead in forfalt[:5]:
            dager = (i_dag - lead.date_deadline).days
            # Navn, ikke ID — husets regel. `display_name` bærer kundenavnet
            # slik brukeren kjenner det, også når navnemønsteret er satt opp
            # per firma (Loym-oppsettet gjør nettopp det).
            linjer.append({
                "tekst": "%s — %s dager over frist" % (lead.display_name, dager),
                "res_id": lead.id,
            })

        return {
            "haster": len(forfalt),
            "i_dag": i_dag_ant,
            "totalt": totalt,
            "linjer": linjer,
        }

    @api.model
    def get_pipeline(self, company_id=False):
        """Pipelinen gruppert per stadium — grunnlaget for selve salgsflaten.

        Stadiene LESES fra basen; de er ikke en liste i koden. Hvert firma
        setter opp sine egne (fiqas kjører ti, fra «000 Inbox» til «4.00 Won»),
        og en hardkodet modell ville vist feil kolonner hos alle andre.

        Hele pipelinen vises — også vunnet og tapt. Her er de på sin plass:
        man skal SE at 25 saker er tapt, det er nyttig. Forskjellen mot
        samleboksen er at boksen skal si «hva må jeg gjøre NÅ», mens
        pipelinen viser «hvor står alt». Derfor merkes avsluttede stadier
        (`avsluttet`), så flaten kan dempe dem framfor å skjule dem.
        """
        selv = self.with_company(company_id) if company_id else self
        Lead = selv.env["crm.lead"]
        avsluttede = selv._avsluttede_stadier(selv).ids

        # _read_group gjør jobben i databasen. Å hente alle leads og telle dem
        # i Python ville gitt samme svar og skalert dårlig.
        grupper = Lead._read_group(
            [
                ("type", "=", "opportunity"),
                ("company_id", "in", (False, selv.env.company.id)),
            ],
            groupby=["stage_id"],
            aggregates=["__count", "expected_revenue:sum"],
        )
        per_stadium = {
            stadium.id: (antall, sum_kr or 0.0)
            for stadium, antall, sum_kr in grupper
            if stadium
        }

        # Alle stadier vises, også de tomme: et hull i pipelinen er informasjon.
        # Rekkefølgen er stadienes egen (`sequence`), ikke alfabetisk.
        ut = []
        for stadium in selv.env["crm.stage"].search([], order="sequence, id"):
            antall, sum_kr = per_stadium.get(stadium.id, (0, 0.0))
            ut.append({
                "id": stadium.id,
                "navn": stadium.display_name,
                "vunnet": bool(stadium.is_won),
                # Avsluttet = vunnet ELLER tapt. Flaten demper disse: de er
                # historikk, ikke arbeid som venter.
                "avsluttet": stadium.id in avsluttede,
                "antall": antall,
                "verdi": sum_kr,
            })
        return ut
