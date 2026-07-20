# -*- coding: utf-8 -*-
"""Datalag for Prosjektoversikt-flaten — WBS-tre med timer mot budsjett.

Hvorfor denne finnes (GUI Prosjekt V0.02, 2026-07-18):
Flaten var en STUBB — `prj.xml` viste bare teksten «Kommer». Modulen var installert,
grønn, med fungerende handling og riktig registrert i KR-menyen — men viste ingenting.
KR-sporet (01.01) målte hele kjeden og fant at feilen ikke lå i menyen: den lå her, i at
det ikke fantes innmat. Lærdom, kanonisert: «installert + grønt + handlingen resolver»
betyr IKKE «flaten viser noe».

🔴 OMSKREVET (GUI Prosjekt V0.03, 2026-07-19) — to feil rettet:

1. FLATEN VAR EN LISTEVISNING. V0.02 leverte tabell over prosjekter → tabell over
   oppgaver. Gjermund: «du har kun knapt gjenskapt listevisning fra Odoo NATIVE!!!»
   Odoo HAR allerede prosjekter i liste. Kravspek batch 15 ber om et WBS-TRE
   (Blokk → Fase → Leilighet → Aktivitet) med timer/budsjett per node.
   → `get_wbs_tre()` under bygger det treet, rekursivt, fra project.task-hierarkiet.

2. FREMDRIFT BLE KAPPET PÅ 100 %. Gammel kode: `min(100.0, (ført / est) * 100.0)`.
   Et prosjekt med 215,9 timer mot budsjett 10 ble vist som «100 % grønn» — et skjult
   22× overforbruk. Det er ikke en visningsfeil; det er å skjule nettopp det varselet
   den som styrer økonomien må se.
   → Kappingen er FJERNET. Ekte tall vises (2159 %), og `budsjett_status` sier «over».
   Fremdriftsstripa klippes visuelt i SCSS — tallet lyver aldri.

KANON «Odoo-native først»: dette laget LESER bare. Det eier ingen forretningslogikk Odoo
alt har, og oppretter ingenting. Slås flaten av, står alle data uendret i Odoos egne visninger.

TENANT-ISOLASJON (kanon): company_id hentes ALDRI som parameter fra klienten. Vi leser
`self.env.companies` (sesjonens tillatte firmaer) og lar Odoos record rules gjøre resten.
Klienten kan SNEVRE INN med `firma_id`, aldri utvide.
"""

from odoo import api, fields, models

# Budsjett-status → fargeakse (kravspek batch 15, linje 198-199).
# Denne aksen er KOST/timer, ikke frist — derfor andre farger enn tids-statusen i batch 08b:
#   blå   = innenfor budsjett (arbeid pågår, timene holder)
#   rød   = OVER budsjett (ført > budsjett) — skal ALDRI skjules
#   grønn = ferdig
#   grå   = ikke startet / ingen budsjett satt
# Ordinal brukes ved rollup: verste status vinner oppover i treet (samme mønster som
# `projStats` i fasit-mockupen docs/mockups/0.00 IQ prosjektoversikt_utkast02.html).
STATUS_ORDINAL = {"over": 3, "innenfor": 2, "ferdig": 1, "plan": 0}


class FiqGuiPrjData(models.AbstractModel):
    _name = "fiq.gui.prj.data"
    _description = "FIQ Prosjektoversikt — datalag (kun lesing)"

    # ---------- intern hjelp ----------

    def _tillatte_firmaer(self):
        """Firmaer sesjonen faktisk har — aldri fra klient-parameter."""
        return self.env.companies.ids or [self.env.company.id]

    def _firma_domene(self, firma_id=None):
        """Domene begrenset til sesjonens firmaer. `firma_id` kan kun snevre inn."""
        tillatte = self._tillatte_firmaer()
        if firma_id and int(firma_id) in tillatte:
            return [("company_id", "=", int(firma_id))]
        return [("company_id", "in", tillatte)]

    def _prosjekt_domene(self, firma_id=None):
        """Prosjekt-domene: firma-scope MINUS maler.

        MALER SKAL ALDRI VISES (AI KTRL-kontrakten: «is_template = True ekskluderes
        automatisk — 0.90-serien er MALER, rør dem aldri»).
        Verifisert 18.07: basen har 150 prosjekter, hvorav 12 er maler. Uten dette
        filteret fylte 0.90-malene hele førstesiden, og ekte prosjekter ble skjøvet ut.
        """
        domene = self._firma_domene(firma_id)
        if "is_template" in self.env["project.project"]._fields:
            domene = domene + [("is_template", "=", False)]
        return domene

    # ---------- budsjett-aksen (kravspek batch 15) ----------

    def _budsjett_status(self, fort, budsjett, ferdig):
        """Fargeakse for budsjett — IKKE for frist.

        🔴 Rekkefølgen er bevisst: OVER BUDSJETT slår ut selv om noden er ferdig.
        En ferdig aktivitet som brukte 3x budsjettet er ikke en suksess å farge grønn —
        det er nettopp den erfaringen neste kalkyle skal bygge på.
        """
        if budsjett > 0 and fort > budsjett:
            return "over"
        if ferdig:
            return "ferdig"
        if budsjett > 0 or fort > 0:
            return "innenfor"
        return "plan"

    def _forbruk_prosent(self, fort, budsjett):
        """Timeforbruk i prosent av budsjett — ALDRI kappet.

        Gammel kode kappet på 100 og skjulte overforbruk. 215,9 timer mot budsjett 10
        SKAL vise 2159 %, ikke «100 % grønn». Stripa klippes i SCSS; tallet er ærlig.
        Uten budsjett gir vi 0.0 og lar `budsjett_status` = «plan» forklare hvorfor —
        en prosentandel av ingenting er meningsløs, ikke null.
        """
        if budsjett <= 0:
            return 0.0
        return round((fort / budsjett) * 100.0, 1)

    # ---------- WBS-treet ----------

    def _node(self, task, barn):
        """Bygg én trenode av en oppgave + dens (ferdigbygde) barn.

        Rollup nedenfra: en forelders timer/budsjett er summen av barnas PLUSS sitt eget.
        Odoo lar deg føre timer på en forelder selv om den har barn, så begge må med —
        ellers forsvinner timer ført direkte på en fase.
        """
        ferdig = bool(task.stage_id.fold) or task.state in ("1_done", "1_canceled")

        egen_fort = task.effective_hours if "effective_hours" in task._fields else 0.0
        egen_budsjett = task.allocated_hours or 0.0

        fort = egen_fort + sum(b["forte_timer"] for b in barn)
        budsjett = egen_budsjett + sum(b["budsjett_timer"] for b in barn)

        status = self._budsjett_status(fort, budsjett, ferdig)

        # Verste status vinner oppover — et rødt barn gjør forelderen rød, ellers ville
        # et enkelt overforbrukt rom druknet i et stort prosjekt som «ser fint ut».
        for b in barn:
            if STATUS_ORDINAL[b["budsjett_status"]] > STATUS_ORDINAL[status]:
                status = b["budsjett_status"]

        return {
            "id": task.id,
            "navn": task.display_name,
            # Oppgavenummer (code) er STABILT; WBS er dynamisk. Aldri bland dem.
            "oppgavenr": task.code or "",
            "wbs": task.fiq_wbs_number or "",
            "ansvarlige": ", ".join(task.user_ids.mapped("name")),
            # 🤖 uten mennesker / 👤 med — samme merking som AI KTRL-kontrakten.
            "er_ai": not bool(task.user_ids),
            "stadium": task.stage_id.display_name or "",
            "ferdig": ferdig,
            "frist": fields.Date.to_string(task.date_deadline) if task.date_deadline else False,
            "forte_timer": round(fort, 1),
            "budsjett_timer": round(budsjett, 1),
            "egne_timer": round(egen_fort, 1),
            "forbruk_prosent": self._forbruk_prosent(fort, budsjett),
            "budsjett_status": status,
            "antall_sjekklister": len(task.fiq_sjekkliste_ids),
            "sjekkliste_fremdrift": round(task.fiq_sjekkliste_fremdrift or 0.0, 1),
            "barn": barn,
        }

    def _bygg_gren(self, task, barn_av):
        """Rekursivt: bygg noden for `task` med hele undertreet.

        `barn_av` er forhåndsgruppert (parent_id -> oppgaver) så vi gjør ÉN spørring
        for hele treet i stedet for én per nivå. Batching er ikke pynt her: SDV-prosjekter
        har fire nivåer (Blokk → Fase → Leilighet → Aktivitet) og hundrevis av noder.
        """
        barn = [self._bygg_gren(b, barn_av) for b in barn_av.get(task.id, [])]
        return self._node(task, barn)

    @api.model
    def get_wbs_tre(self, prosjekt_id, firma_id=None):
        """WBS-treet for ett prosjekt — Blokk → Fase → Leilighet → Aktivitet.

        Kravspek batch 15 (docs/0.00 IQ kontrollrom_flate_spec.md, linje 195-197):
        «WBS-tre som driller: Blokk → Fase → Leilighet → Aktivitet. Foldbart per nivå.
        Per node: Effektive timer / Budsjett + fremdriftsbar.»

        Hierarkiet er Odoos EGET (`parent_id` på project.task) — vi finner ikke opp en
        ny struktur. Rekkefølgen følger `fiq_wbs_number` slik brukeren ser den i native
        views, ikke intern id.
        """
        domene = self._firma_domene(firma_id) + [("project_id", "=", int(prosjekt_id))]
        alle = self.env["project.task"].search(
            domene, order="fiq_wbs_number, sequence, id"
        )

        # Grupper barn per forelder i ett sveip. Merk: en oppgave hvis forelder ligger
        # UTENFOR domenet (annet firma/prosjekt) må behandles som rot — ellers blir den
        # usynlig i treet, og timene forsvinner fra rollupen.
        i_settet = set(alle.ids)
        barn_av = {}
        rotter = []
        for t in alle:
            if t.parent_id and t.parent_id.id in i_settet:
                barn_av.setdefault(t.parent_id.id, []).append(t)
            else:
                rotter.append(t)

        noder = [self._bygg_gren(t, barn_av) for t in rotter]

        prosjekt = self.env["project.project"].browse(int(prosjekt_id))
        sum_fort = sum(n["forte_timer"] for n in noder)
        sum_budsjett = sum(n["budsjett_timer"] for n in noder)

        # Prosjektets eget budsjett (allocated_hours) er FASIT der det er satt —
        # oppgavesummen er et anslag som ofte er ufullstendig.
        prosjekt_budsjett = prosjekt.allocated_hours or 0.0
        budsjett = prosjekt_budsjett or sum_budsjett

        return {
            "prosjekt": {
                "id": prosjekt.id,
                "navn": prosjekt.display_name,
                "nummer": prosjekt.sequence_code or "",
                "kunde": prosjekt.partner_id.display_name or "",
                "firma": prosjekt.company_id.display_name or "",
                "forte_timer": round(sum_fort, 1),
                "budsjett_timer": round(budsjett, 1),
                "forbruk_prosent": self._forbruk_prosent(sum_fort, budsjett),
                "budsjett_status": self._budsjett_status(
                    sum_fort, budsjett, all(n["ferdig"] for n in noder) if noder else False
                ),
                "budsjett_kilde": "prosjekt" if prosjekt_budsjett else "oppgaver",
            },
            "noder": noder,
            "antall_noder": len(alle),
        }

    # ---------- AI-arbeid som PROSJEKT (Gjermund-direktiv 2026-07-20) ----------

    @api.model
    def get_ai_arbeid(self, firma_id=None):
        """AI-sporene vist som ARBEID — aldri som øktnummer.

        🔴 GJERMUND-DIREKTIV 20.07.2026, ordrett:
            «Kan jeg ikke bruke prosjekter og så kan claude gjøre hva det vil?»
            «pktsystemet til Claude kan dra et vist mørk plass.»
            «i da!!!!!!! det har kostet dager med ekstra arbide og over 100 timer»

        Problemet: øktnummeret («01.02», «00.03») er CLAUDES bokføring, men Gjermund
        tvinges til å forholde seg til det. Verre: nummeret FLYTTER SEG mens arbeidet
        står stille — en referanse skrevet i dag peker på en død økt i morgen.
        Øktnummeret ER en id ([[feedback-names-not-ids]]); vi har bare ikke behandlet
        den som en.

        Løsningen: han ser «Kontrollrom», «Salg», «Kommunikasjon» — navn på ARBEID,
        med fremdrift og historikk. Hvilken Claude-økt som utfører er en teknisk
        detalj han aldri møter.

        Arbeidsdeling avtalt med AI KR (00.04) 20.07: de eier `fiq.ai.spor` og feltet
        `project_id` på den; vi eier flaten som viser det. Ingen ny datamodell —
        `project.project` overlever allerede at utføreren byttes, og det er nettopp
        derfor det er riktig hjem.

        🛑 KANON: prosjekter opprettes ALDRI maskinelt (wizard/regelmotor eier flyten).
        Denne metoden LESER bare. Et spor uten prosjekt vises ærlig som ukoblet —
        vi lager ikke et tomt prosjekt for å fylle et felt.
        """
        Spor = self.env.get("fiq.ai.spor")
        if Spor is None:
            # fiq_gui_ai_kr ikke installert — flaten skal ikke falle av det.
            return {"spor": [], "tilgjengelig": False}

        firmaer = self._tillatte_firmaer()
        valgt = int(firma_id) if firma_id and int(firma_id) in firmaer else False

        try:
            rader = Spor.get_spor_som_prosjekt(company_id=valgt)
        except AttributeError:
            # Eldre fiq_gui_ai_kr (< 19.0.2.10.0) mangler metoden.
            return {"spor": [], "tilgjengelig": False}

        ut = []
        for s in rader:
            pid = s.get("project_id") or False
            ut.append({
                "id": s.get("id"),
                # Navn på arbeidet — det Gjermund faktisk kjenner igjen.
                "navn": s.get("prosjekt") or s.get("navn") or "",
                "kode": s.get("kode") or "",
                "versjon": s.get("versjon") or "",
                "status": s.get("status") or "",
                "modul": s.get("modul") or "",
                "i_odoo": bool(s.get("i_odoo")),
                "project_id": pid,
                # Ukoblet spor sies ÆRLIG. Alternativet — å skjule det — ville gitt
                # et bilde som ser komplett ut mens noe mangler.
                "koblet": bool(pid),
                "beskrivelse": s.get("beskrivelse") or "",
                # 🛑 `aktive_okter` er med som TALL (hvor mye som skjer), aldri som
                # øktnummer. Ingen «01.02» passerer dette laget.
                "aktivitet": s.get("aktive_okter") or 0,
            })

        return {
            "spor": ut,
            "tilgjengelig": True,
            "antall": len(ut),
            "antall_koblet": sum(1 for s in ut if s["koblet"]),
            "valgt_firma": valgt,
        }

    # ---------- offentlig API for flaten ----------

    @api.model
    def get_prosjektoversikt(self, firma_id=None, grense=50):
        """Prosjekter med timer mot budsjett, oppgavetelling og frister.

        🔴 ENDRET V0.03: `fremdrift` (kappet på 100) er erstattet av `forbruk_prosent`
        (ekte tall) + `budsjett_status` (blå/rød/grønn). Se modulens toppkommentar.
        `fremdrift_kilde` beholdes — brukeren skal fortsatt se om tallet er fasit
        (timer) eller anslag (oppgaveandel).
        """
        Project = self.env["project.project"]
        domene = self._prosjekt_domene(firma_id)
        prosjekter = Project.search(domene, limit=int(grense), order="name")

        rader = []
        for p in prosjekter:
            oppgaver = p.task_ids
            ferdige = oppgaver.filtered(
                lambda t: t.stage_id.fold or t.state in ("1_done", "1_canceled")
            )
            est = p.allocated_hours or 0.0
            fort = p.effective_hours if "effective_hours" in p._fields else 0.0
            alt_ferdig = bool(oppgaver) and len(ferdige) == len(oppgaver)

            # Rekkefølgen er bevisst: timer er FASIT, oppgaveandel er et ANSLAG.
            # Krav: est > 0. Verifisert 18.07 at de fleste prosjekter har
            # allocated_hours = 0 — da er «0 % beregnet fra timer» meningsløst og
            # direkte villedende. Uten denne sjekken viste et prosjekt med 66
            # oppgaver «0,0 % (timer)», som så ut som en feil i dataene.
            if est > 0:
                kilde = "timer"
            elif oppgaver:
                kilde = "oppgaver"
            else:
                kilde = "ingen"

            # Andel ferdige oppgaver — brukes som fremdriftsbar der budsjett mangler.
            andel_ferdig = (
                round((len(ferdige) / len(oppgaver)) * 100.0, 1) if oppgaver else 0.0
            )

            rader.append({
                "id": p.id,
                "navn": p.display_name,
                # Navn, ikke ID — husets regel. Prosjektnummeret er STABILT (røres aldri).
                "nummer": p.sequence_code or "",
                "firma": p.company_id.display_name or "",
                "firma_id": p.company_id.id,
                "kunde": p.partner_id.display_name or "",
                "antall_oppgaver": len(oppgaver),
                "antall_ferdige": len(ferdige),
                "budsjett_timer": round(est, 1),
                "forte_timer": round(fort, 1),
                # 🔴 ALDRI kappet — se _forbruk_prosent.
                "forbruk_prosent": self._forbruk_prosent(fort, est),
                "budsjett_status": self._budsjett_status(fort, est, alt_ferdig),
                "andel_ferdig": andel_ferdig,
                "fremdrift_kilde": kilde,
                "frist": fields.Date.to_string(p.date) if p.date else False,
            })
        return {
            "prosjekter": rader,
            "firmaer": [
                {"id": c.id, "navn": c.display_name}
                for c in self.env["res.company"].browse(self._tillatte_firmaer())
            ],
            "valgt_firma": int(firma_id) if firma_id else False,
            "antall_totalt": Project.search_count(self._prosjekt_domene(firma_id)),
        }

    @api.model
    def get_oppgaver(self, prosjekt_id, firma_id=None):
        """Oppgavene i ett prosjekt, flatt, sortert etter disposisjonsnummer (WBS).

        BEHOLDT for bakoverkompatibilitet — `get_wbs_tre` er den flaten bruker nå.
        Sorteringen bruker `fiq_wbs_number` slik brukeren ser treet — ikke intern id.
        """
        domene = self._firma_domene(firma_id) + [("project_id", "=", int(prosjekt_id))]
        oppgaver = self.env["project.task"].search(domene, order="fiq_wbs_number, sequence, id")

        rader = []
        for t in oppgaver:
            fort = t.effective_hours if "effective_hours" in t._fields else 0.0
            budsjett = t.allocated_hours or 0.0
            ferdig = bool(t.stage_id.fold)
            rader.append({
                "id": t.id,
                "navn": t.display_name,
                # Oppgavenummer (code) er STABILT; WBS er dynamisk. Aldri bland dem.
                "oppgavenr": t.code or "",
                "wbs": t.fiq_wbs_number or "",
                "ansvarlige": ", ".join(t.user_ids.mapped("name")),
                "er_ai": not bool(t.user_ids),
                "stadium": t.stage_id.display_name or "",
                "ferdig": ferdig,
                "frist": fields.Date.to_string(t.date_deadline) if t.date_deadline else False,
                "prioritet": t.priority,
                "budsjett_timer": round(budsjett, 1),
                "forte_timer": round(fort, 1),
                "forbruk_prosent": self._forbruk_prosent(fort, budsjett),
                "budsjett_status": self._budsjett_status(fort, budsjett, ferdig),
                "antall_sjekklister": len(t.fiq_sjekkliste_ids),
                "sjekkliste_fremdrift": round(t.fiq_sjekkliste_fremdrift or 0.0, 1),
            })
        prosjekt = self.env["project.project"].browse(int(prosjekt_id))
        return {
            "prosjekt": {"id": prosjekt.id, "navn": prosjekt.display_name},
            "oppgaver": rader,
        }
