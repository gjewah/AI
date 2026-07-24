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

    # ---------- prioritet: ÉN sannhet, én form ----------

    # Lovlige verdier flaten kan tegne (prj.js prioSymbol: h ▴ · m ▪ · l ▾).
    # Alt annet må falle til «m» — en ukjent verdi ville gitt et symbol-fall
    # uten feilmelding, som er den stille varianten av en feil.
    PRIORITET_LOVLIG = ("h", "m", "l")

    def _prioritet(self, task):
        """Prioritet i ÉN form: «h» · «m» · «l». Aldri Odoos rå «0»/«1».

        🔴 RETTET 23.07: datalaget sendte TO ULIKE FORMER for samme begrep —
        `get_oppgaver_over_tid` mappet til «h»/«m», mens `get_oppgaver` sendte
        `t.priority` rått («0»/«1»). Klienten kunne ikke vite hvilken den fikk.
        `prioSymbol("1")` traff verken «h» eller «l» og falt til ▪ — feil
        symbol, ingen feilmelding, ingen som merket det.

        🔑 Samme klasse som kortslutningene i 1.31.0: to utganger, to former.
        Fiksen er den samme — ÉN metode som alle utganger går gjennom, så en
        endring i formen ikke kan treffe det ene stedet og ikke det andre.

        Feltet er `required=True` med default «m», så en tom verdi skal ikke
        finnes. Vakten står likevel: et felt som er påkrevd i dag kan bli
        valgfritt i morgen, og da skal flaten fortsatt tegne noe riktig.
        """
        if "fiq_prioritet" not in task._fields:
            # Modulen som eier feltet er ikke lastet (skal ikke kunne skje her,
            # men datalaget skal aldri felle flaten på en manglende nabo).
            return "m"
        verdi = task.fiq_prioritet
        return verdi if verdi in self.PRIORITET_LOVLIG else "m"

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
            "oppgavenr": (task.code or "") if "code" in task._fields else "",
            "wbs": task.fiq_wbs_number or "",
            "ansvarlige": ", ".join(task.user_ids.mapped("name")),
            # 🤖 uten mennesker / 👤 med — samme merking som AI KTRL-kontrakten.
            "er_ai": not bool(task.user_ids),
            "stadium": task.stage_id.display_name or "",
            "ferdig": ferdig,
            "frist": fields.Date.to_string(task.date_deadline.date()) if task.date_deadline else False,
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

    # ---------- FLATEN: oppgaver over tid (fasit utkast03) ----------

    def _iso_uke(self, d):
        """(år, ukenummer) for en dato — ISO, som resten av huset."""
        iso = d.isocalendar()
        return (iso[0], iso[1])

    def _tid_status(self, task, ferdig, i_dag):
        """Status på TIDSAKSEN — ikke budsjett-aksen.

        Fasiten (utkast03) viser fire: i rute · følg opp · kritisk · planlagt.
        Dette er en ANNEN akse enn `budsjett_status` (blå/rød/grønn på timer).
        Å blande dem var nettopp feilen i batch 08b vs batch 15 — frist og kost
        er to spørsmål, og en oppgave kan være i rute på tid mens den sprenger
        budsjettet.
        """
        if ferdig:
            return "rute"

        # 🔴 KRASJET fiqas Staging 21.07 kl. 22:58 (feilklasse 8: data-betinget krasj).
        # `date_deadline` er **Datetime** i Odoo 19 (verifisert i kilden:
        # project/models/project_task.py:183, og i ir_model_fields = «datetime»),
        # mens `i_dag` er en **Date**. `datetime < date` gir TypeError.
        # Hele get_oppgaver_over_tid kastet 500 → flaten fikk ingen data → blank skjerm.
        #
        # Hvorfor testene var grønne: uten frister på oppgavene returnerte metoden på
        # linja over («if not frist»), og sammenligningen ble aldri nådd. Etter rebuild
        # fra Production fantes ekte frister — og første kall smalt.
        # 👉 Test alltid mot en oppgave som FAKTISK har frist satt.
        frist = task.date_deadline
        if not frist:
            har_start = ("planned_date_begin" in task._fields
                         and task.planned_date_begin)
            return "rute" if har_start else "plan"
        frist = frist.date()  # Datetime -> Date, samme type som i_dag

        if frist < i_dag:
            return "krit"
        # Innenfor sju dager = «følg opp». Fasitens «Frister denne uka».
        if (frist - i_dag).days <= 7:
            return "folg"
        return "rute"

    def _risiko_dom(self, fort, budsjett, fremdrift, naermeste_frist, i_dag,
                    ferdig=False):
        """Én dom om et prosjekt: er det trangt på penger eller tid?

        🔑 FASITEN KREVER EN DOM, IKKE ET TALL (AI KR + AI PK 23.07):

            26_042 Kabelgata   62 % brukt / 62 % fremdrift        → i balanse
            26_015 BUF         0,9M / 2,1M · men EM-frist i dag   → tett tid
            24_055 Oscarsgate  tilbud ute — frist i dag kl 15     → avgjøres i dag
            26_014 Rådhusgata  0,6M / 1,8M · Per sykmeldt tor-fre → bemanning

        Vi HADDE tallene (`forbruk_prosent`, `budsjett_status`) og trodde det var
        levert. Det var det ikke: Gjermund skal ikke lese to tall og regne selv.
        Fasitens egen fotnote sier hvorfor flaten finnes i det hele tatt —
        «med det Odoo IKKE gir: … risiko når budsjett eller tid er trangt».
        En Gantt som gir det Odoo alt gir, trenger vi ikke.

        🛑 DOMMEN ER IKKE SAMME AKSE SOM `budsjett_status`. Den er en TREDJE akse:
            TID   (i rute / følg opp / kritisk)      — rekker vi fristen
            KOST  (innenfor / over / ferdig)         — holder budsjettet
            RISIKO (denne)                           — hva bør du GJØRE noe med
        Et prosjekt kan ligge under budsjett og likevel være det som haster mest,
        fordi fristen er i morgen. Å slå dem sammen ville skjult nettopp det.

        `bemanning` returneres ALDRI herfra. Fasiten viser den, men den bygger på
        ressursdata (sykefravær, dobbeltbooking) som krever
        `planlegging_ressurs_spec` — UTKAST 01 siden 04.07, ubesvart. Å gjette
        bemanning fra timeføring ville vært å presentere en antagelse som en dom.
        📌 Blokkeringen er meldt AI PK som større enn tidligere rapportert.
        """
        if ferdig:
            return "ferdig"

        # Frist først: en frist i dag eller passert slår alt annet. Det er den
        # eneste dommen som ikke tåler å vente til i morgen.
        if naermeste_frist:
            dager = (naermeste_frist - i_dag).days
            if dager <= 0:
                return "avgjores"
            if dager <= 3:
                return "tett_tid"

        # Så penger: brukt mer enn budsjettet er alltid rødt.
        if budsjett > 0:
            brukt = (fort / budsjett) * 100.0
            if brukt > 100.0:
                return "over_budsjett"
            # 🔑 KJERNEN I DOMMEN: forbruk mot FREMDRIFT, ikke mot budsjett alene.
            # 62 % brukt av 62 % ferdig = i balanse. 62 % brukt av 20 % ferdig er
            # på vei mot sprekk selv om ingen grense er passert ennå. Det er
            # nettopp dette Odoo ikke sier fra om.
            # 🔴 `fremdrift > 0` sto her som vakt mot manglende data. Den slapp
            # gjennom det VERSTE tilfellet: penger brukt uten at noe er gjort.
            # Funnet 23.07 ved å lese ekte rader etter at testene var grønne —
            # «36 % brukt / 0 % fremdrift» ble meldt som «i balanse».
            # Ingen av mine ni tester hadde fremdrift = 0. Grønne tester på en
            # sak de aldri stilte.
            if brukt - fremdrift >= 20.0:
                return "tett_budsjett"

        return "i_balanse"

    def _risiko_hvorfor(self, fort, budsjett, fremdrift, naermeste_frist, i_dag,
                        ferdig=False):
        """Begrunnelsen bak dommen, i klartekst.

        Fasiten viser ALDRI merket alene — den viser hvorfor:
            «62 % brukt / 62 % fremdrift»   «EM-frist i dag»   «0,4M / 0,9M»

        🔑 Et merke uten begrunnelse er bare et nytt tall å tolke. Gjermund skal
        kunne lese linja og vite hva han skal gjøre — ikke måtte åpne prosjektet
        for å finne ut hvorfor det er rødt. Plain språk, ingen forkortelser.
        """
        if ferdig:
            return "alle oppgaver ferdige"

        deler = []
        if naermeste_frist:
            dager = (naermeste_frist - i_dag).days
            if dager < 0:
                deler.append(f"frist passert for {abs(dager)} dager siden")
            elif dager == 0:
                deler.append("frist i dag")
            elif dager == 1:
                deler.append("frist i morgen")
            elif dager <= 3:
                deler.append(f"frist om {dager} dager")

        if budsjett > 0:
            brukt = (fort / budsjett) * 100.0
            deler.append(f"{brukt:.0f} % brukt / {fremdrift:.0f} % fremdrift")
        elif fort > 0:
            # Timer ført uten budsjett: ikke en dom, men verdt å si. Uten dette
            # ville linja stått tom og sett ut som manglende data.
            deler.append(f"{fort:.1f} timer ført, uten budsjett")

        return " · ".join(deler) if deler else "ingen frist eller budsjett satt"

    @api.model
    def get_oppgaver_over_tid(self, firma_id=None, fra_uke=None, antall=7,
                              oppløsning="uke", grupper="prosjekt", grense=400):
        """Alle oppgaver med tidsplassering — grunnlaget for Gantt/Liste/Kanban.

        Fasit: `docs/mockups/0.00 IQ prosjektoversikt_utkast03.html` (artifact 87871eef),
        kartlagt ved å klikke alle 122 kontroller. Se
        `docs/0.00 IQ prj_flate_kravspek_KOMPLETT.md`.

        TRE VISNINGER × TO AKSER deler ETT datasett — det er hele poenget. Gantt,
        Liste og Kanban er ulike tegninger av de samme radene, akkurat som i fasiten
        (`renderGantt` / `renderListe` / `renderKanban` leser samme TASKS-array).
        Klienten bytter visning uten ny spørring.

        `oppløsning`:
          «uke»  → `antall` uker fra `fra_uke` (fasit: 7 kolonner)
          «mnd»  → `antall` måneder à 4 uker (fasit: 6 kolonner, ett steg = 4 uker)

        🛑 Firma-scope FØRST — før gruppering, før visning. Klienten kan kun snevre inn.
        """
        from datetime import date, datetime, timedelta

        i_dag = fields.Date.context_today(self)

        # --- tidsvindu ---
        if fra_uke:
            try:
                aar, uke = [int(x) for x in str(fra_uke).split("-")]
                start = date.fromisocalendar(aar, uke, 1)
            except (ValueError, TypeError):
                start = i_dag - timedelta(days=i_dag.weekday())
        else:
            # Default: uka vi står i, slik «I dag» i fasiten lander.
            start = i_dag - timedelta(days=i_dag.weekday())

        antall = max(1, min(int(antall or 7), 26))
        uker_per_kol = 4 if oppløsning == "mnd" else 1
        slutt = start + timedelta(weeks=antall * uker_per_kol)

        # --- kolonner (tidsaksen flaten tegner) ---
        kolonner = []
        for i in range(antall):
            k_start = start + timedelta(weeks=i * uker_per_kol)
            k_slutt = k_start + timedelta(weeks=uker_per_kol) - timedelta(days=1)
            aar, uke = self._iso_uke(k_start)
            if oppløsning == "mnd":
                _, sluttuke = self._iso_uke(k_slutt)
                etikett = k_start.strftime("%b")
                under = f"uke {uke}–{sluttuke} · {aar}"
            else:
                etikett = f"Uke {uke}"
                under = str(aar)
            kolonner.append({
                "etikett": etikett,
                "under": under,
                "fra": fields.Date.to_string(k_start),
                "til": fields.Date.to_string(k_slutt),
                "er_naa": k_start <= i_dag <= k_slutt,
            })

        # --- oppgavene ---
        # Bare oppgaver som BERØRER vinduet. Uten dette henter vi hele historikken
        # og lar klienten kaste 95 % — samme feil som å laste alle 150 prosjekter
        # for å vise fem.
        # 🔴 GRENSENE MÅ VÆRE DATETIME — `planned_date_begin` og `date_deadline` er
        # Datetime i Odoo 19 (verifisert i ir_model_fields, se
        # brain/odoo19_dato_felttyper_FAKTA.md).
        #
        # Et rent `date`-objekt tolkes som MIDNATT. Verifisert mot basen 22.07:
        #     <= date(2026,7,21)                 → 463
        #     <= datetime(2026,7,21, 00:00:00)   → 463   ← identisk, altså midnatt
        #     <= datetime(2026,7,21, 23:59:59)   → 463
        # I dag er tallene like fordi ALLE frister i basen står på midnatt (0 oppgaver
        # har klokkeslett). Men første gang noen setter frist kl. 15:00, forsvinner den
        # STILLE ut av siste kolonne — uten feilmelding, uten at noen merker det.
        #
        # Samme klasse som Kommunikasjons fredags-frister som forsvant fra ukesplanen
        # (`fiq_gui_epost_data.py`, `_ukesplan_for_partner`). Tredje gang i huset.
        # Meldt av KR 22.07 før det rakk å bli et ekte tap her.
        start_dt = datetime.combine(start, datetime.min.time())
        slutt_dt = datetime.combine(slutt, datetime.max.time())

        # 🔴 MÅLT 22.07: av 400 returnerte oppgaver kunne bare 21 TEGNES.
        # 379 hadde verken `planned_date_begin` eller `date_deadline` — de kom med
        # fordi det gamle domenet hadde `("date_deadline", "=", False)` som eget
        # OR-ledd, altså «ta med alt uten frist».
        #
        # Konsekvensen i flaten: 379 rader uten søyle. Gantt-en så nesten tom ut,
        # og KPI-ene summerte til 21 av 400 — resten falt i «plan» uten å bety noe.
        # En tidslinje som viser rader uten tid er ikke en tidslinje.
        #
        # NÅ: en oppgave må ha MINST ÉN dato for å høre hjemme på tidsaksen, og
        # den datoen må berøre vinduet:
        #   · start i vinduet (planned_date_begin <= slutt), ELLER
        #   · frist i vinduet (date_deadline >= start)
        # Udaterte oppgaver finnes fortsatt i Liste og Kanban via get_prosjektoversikt
        # og get_wbs_tre — de er ikke borte, de hører bare ikke hjemme i en Gantt.
        # 🔴 `planned_date_begin` kommer fra `project_enterprise` og finnes IKKE alltid.
        # Fanget på Dev 22.07 — der er modulen uninstalled, og domenet kastet
        # `KeyError: 'planned_date_begin'` inne i Odoos domene-parser.
        #
        # Staging viste det aldri, fordi Enterprise er installert der. Det er hele
        # grunnen til at Dev-leddet finnes: en modul som er «grønn» mot en rik base
        # kan være ubrukelig på en mager. KANON «Odoo-native først» sier at flaten
        # skal virke uten tilleggsmoduler — ikke bare uten KR.
        Task = self.env["project.task"]
        har_start = "planned_date_begin" in Task._fields

        dato_ledd = [
            "&", ("date_deadline", "!=", False),
                 ("date_deadline", ">=", start_dt),
        ]
        if har_start:
            dato_ledd = ["|",
                "&", ("planned_date_begin", "!=", False),
                     ("planned_date_begin", "<=", slutt_dt),
            ] + dato_ledd

        domene = self._firma_domene(firma_id) + [("project_id", "!=", False)] + dato_ledd

        # `fiq_wbs_number` er vårt eget felt og finnes alltid; `sequence` og `id` er native.
        oppgaver = Task.search(
            domene, limit=int(grense), order="project_id, fiq_wbs_number, sequence, id"
        )

        rader = []
        for t in oppgaver:
            ferdig = bool(t.stage_id.fold) or t.state in ("1_done", "1_canceled")
            fort = t.effective_hours if "effective_hours" in t._fields else 0.0
            budsjett = t.allocated_hours or 0.0

            # 🔴 BEGGE er Datetime i Odoo 19 — konverter til Date FØR bruk.
            # `b` gjorde det allerede; `e` gjorde det ikke, og blandet dermed
            # Datetime og Date i samme rad. Klienten regner på disse som datoer.
            pdb = t.planned_date_begin if "planned_date_begin" in t._fields else False
            b = pdb.date() if pdb else None
            frist_d = t.date_deadline.date() if t.date_deadline else None
            e = frist_d or b

            rader.append({
                "id": t.id,
                "navn": t.display_name,
                # Tre tall side om side — fasitens «01.01 · T0412 · 2026-00084».
                "wbs": t.fiq_wbs_number or "",
                "oppgavenr": (t.code or "") if "code" in t._fields else "",
                "prosjektnr": t.project_id.sequence_code or "",
                "prosjekt": t.project_id.display_name or "",
                "prosjekt_id": t.project_id.id,
                "firma": t.company_id.display_name or "",
                "firma_id": t.company_id.id,
                "ansvarlig": ", ".join(t.user_ids.mapped("name")),
                # 🤖 uten mennesker / 👤 med — samme merking som AI KTRL-kontrakten.
                "er_ai": not bool(t.user_ids),
                "stadium": t.stage_id.display_name or "",
                "ferdig": ferdig,
                "fra": fields.Date.to_string(b) if b else False,
                "til": fields.Date.to_string(e) if e else False,
                "frist": fields.Date.to_string(t.date_deadline.date()) if t.date_deadline else False,
                # Tre nivåer (▴▪▾) fra vårt eget felt — AI PK avgjorde 23.07 at
                # Odoos binære `priority` ikke kan bære dem. Se
                # models/project_task_prioritet.py.
                "prioritet": self._prioritet(t),
                "fremdrift": round(min(100.0, t.progress or 0.0), 1),
                "forte_timer": round(fort, 1),
                "budsjett_timer": round(budsjett, 1),
                "forbruk_prosent": self._forbruk_prosent(fort, budsjett),
                "budsjett_status": self._budsjett_status(fort, budsjett, ferdig),
                "tid_status": self._tid_status(t, ferdig, i_dag),
                "antall_sjekklister": len(t.fiq_sjekkliste_ids),
                "sjekkliste_fremdrift": round(t.fiq_sjekkliste_fremdrift or 0.0, 1),
            })

        # --- KPI (fasitens fem kort, alle klikkbare) ---
        i_rute = sum(1 for r in rader if r["tid_status"] == "rute" and not r["ferdig"])
        folg = sum(1 for r in rader if r["tid_status"] == "folg")
        krit = sum(1 for r in rader if r["tid_status"] == "krit")
        denne_uka = start + timedelta(days=6)
        frister = sum(
            1 for r in rader
            if r["frist"] and start <= fields.Date.from_string(r["frist"]) <= denne_uka
        )
        ai_gjort = sum(1 for r in rader if r["er_ai"] and r["ferdig"])
        ai_totalt = sum(1 for r in rader if r["er_ai"])
        fra_aar, fra_uke_nr = self._iso_uke(start)

        return {
            "kolonner": kolonner,
            "oppgaver": rader,
            "opplosning": oppløsning,
            "grupper": grupper,
            # 🔑 `_iso_uke` gir en TUPPEL (år, uke). `%`-operatoren pakket den ut
            # automatisk; en f-streng gjør ikke det — verdiene må hentes hver for
            # seg, ellers ville hele tuppelen blitt skrevet som «(2026, 30)».
            # Rekkefølgen er år-uke, samme som før: «2026-30».
            "fra_uke": f"{fra_aar}-{fra_uke_nr}",
            "i_dag": fields.Date.to_string(i_dag),
            "kpi": {
                "i_rute": i_rute,
                "folg_opp": folg,
                "kritisk": krit,
                "frister_uka": frister,
                "ai_gjort": ai_gjort,
                "ai_totalt": ai_totalt,
            },
            "firmaer": [
                {"id": c.id, "navn": c.display_name}
                for c in self.env["res.company"].browse(self._tillatte_firmaer())
            ],
            "valgt_firma": int(firma_id) if firma_id else False,
            "antall": len(rader),
            # Ærlig når vi har kappet: brukeren skal vite at han ser et utsnitt.
            "avkortet": len(rader) >= int(grense),
        }

    # ---------- SJEKKLISTE-PANELET (fasit utkast03) ----------

    @api.model
    def get_sjekklister(self, oppgave_id, firma_id=None):
        """Sjekklistene på én oppgave — grunnlaget for sprettopp-panelet.

        Fasiten viser ÉN liste med TO flater:
          🖥 Prosjekteier — «legger til punkter»: nummerert, krav-merker, ＋ Legg til
          📱 Arbeider     — «kvitterer ut UTEN Odoo-lisens»: stor hake, ✍ Signer

        Dette laget LESER bare. Motoren (`fiq.sjekkliste`, AI KRs arbeid) eier all
        logikk: krav-constraint, versjonsbump, maler, kvittering. Vi gjenskaper
        ingenting av det — flaten er en pen inngang til de samme dataene.

        🛑 Firma-scope FØRST, som overalt ellers. Oppgaven må ligge i et firma
        sesjonen har, ellers får man ingenting — ikke en tom liste som ser normal ut.
        """
        Sjekk = self.env.get("fiq.sjekkliste")
        if Sjekk is None:
            # 🔴 Samme feil som i get_ai_arbeid, funnet i samme gjennomgang:
            # denne grenen manglet `oppgave`, mens de to andre returnerte den.
            # Tre utganger, tre ulike former. Klienten må kunne lese samme
            # nøkler uansett hvilken vei den gikk.
            return {"tilgjengelig": False, "lister": [], "oppgave": False}

        domene = self._firma_domene(firma_id) + [("id", "=", int(oppgave_id))]
        oppgave = self.env["project.task"].search(domene, limit=1)
        if not oppgave:
            return {"tilgjengelig": True, "lister": [], "oppgave": False}

        lister = []
        for s in oppgave.fiq_sjekkliste_ids:
            punkter = []
            for p in s.punkt_ids.sorted(key=lambda x: (x.sequence, x.id)):
                # Kravene er UAVHENGIGE (Gjermund 16.07): dok / foto / signatur.
                # FDV og klima ER dokumenter — ikke bilder.
                krav = []
                if p.krav_dok:
                    krav.append("dok")
                if p.krav_foto:
                    krav.append("foto")
                if p.krav_sign:
                    krav.append("sign")
                punkter.append({
                    "id": p.id,
                    "navn": p.name or "",
                    "beskrivelse": p.beskrivelse or "",
                    "utfoert": bool(p.utfoert),
                    "krav": krav,
                    # Motorens egen constraint avgjør om punktet KAN kvitteres.
                    # Flaten viser sperren; den finner den ikke opp.
                    "kan_kvitteres": bool(p.kan_kvitteres),
                    "mangler": p.mangler or "",
                    "har_dok": bool(p.kvitt_dok_id),
                    "har_foto": bool(p.kvitt_foto_id),
                    "signert_av": p.kvitt_sign_av or "",
                    "kvittert_av": p.kvitt_av or "",
                })
            lister.append({
                "id": s.id,
                "navn": s.name or "",
                "nivaa": s.nivaa or "",
                "type": s.type_liste or "",
                "versjon": s.versjon or "1.0",
                "er_mal": bool(s.er_mal),
                "antall": s.antall_punkt,
                "antall_ok": s.antall_ok,
                "fremdrift": round(s.fremdrift or 0.0, 1),
                "punkter": punkter,
            })

        return {
            "tilgjengelig": True,
            "oppgave": {
                "id": oppgave.id,
                "navn": oppgave.display_name,
                "wbs": oppgave.fiq_wbs_number or "",
                "oppgavenr": (oppgave.code or "") if "code" in oppgave._fields else "",
                "prosjekt": oppgave.project_id.display_name or "",
            },
            "lister": lister,
            "antall_lister": len(lister),
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
            #
            # 🔴 RETTET 23.07: kortslutningen manglet `valgt_firma` og
            # `antall_koblet`, så metoden returnerte TO ULIKE FORMER avhengig av
            # om en annen modul var installert. Klienten kan ikke skrive
            # `res.valgt_firma` uten å vite hvilken gren den havnet i.
            #
            # 🔑 Fanget av en test som krevde nøkkelen alltid — på et FERSKT
            # bygg der AI KR sto uinstallert. På det gamle bygget var AI KR
            # installert, så grenen ble aldri kjørt og testen alltid grønn.
            # Samme klasse som `fremdrift = 0`: kodeveien fantes, men ingen
            # test hadde vært i den. Et tomt bygg er ikke en ulempe — det er
            # den eneste måten å oppdage hva som bare virker ved flaks.
            return {
                "spor": [],
                "tilgjengelig": False,
                "valgt_firma": False,
                "antall_koblet": 0,
            }

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

        # Brukerens dato, ikke serverens. En frist «i dag» skal bety i dag der
        # brukeren sitter — serveren kjører UTC og ligger to timer bak om sommeren.
        i_dag = fields.Date.context_today(self)

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

            # Nærmeste frist blant oppgaver som IKKE er ferdige. En passert frist på
            # en avsluttet oppgave er ikke en risiko — den er historie.
            # `.date()` FØR sammenligning: date_deadline er Datetime (Odoo 19).
            frister = [
                t.date_deadline.date()
                for t in (oppgaver - ferdige)
                if t.date_deadline
            ]
            naermeste = min(frister) if frister else None

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
                # ── RISIKO-DOMMEN (krav 7) ───────────────────────────────────
                # Nærmeste frist blant UFERDIGE oppgaver — ikke prosjektets egen
                # `date`. 🔴 `project.project.date` er en **Date**, mens
                # `project.task.date_deadline` er **Datetime**. Motsatt av hva
                # navnene antyder; verifisert i kilden. Blandes de, får vi samme
                # TypeError som felte Staging 21.07.
                # Prosjektets `date` er ofte tom mens oppgavene har ekte frister —
                # da ville dommen sagt «i balanse» om noe som forfaller i morgen.
                "risiko": self._risiko_dom(
                    fort, est, andel_ferdig, naermeste, i_dag, alt_ferdig,
                ),
                "risiko_hvorfor": self._risiko_hvorfor(
                    fort, est, andel_ferdig, naermeste, i_dag, alt_ferdig,
                ),
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
    def get_kr_boks(self, firma_id=None):
        """Prosjektets fire tall til Kontrollrommets forside «Hvordan ligger vi an».

        Fasit: `docs/mockups/0.00 IQ demo_kontrollrom_08.html:195`, lest i kilden
        23.07 — ikke gjenfortalt fra en melding:

            Prosjekter i rute   18 / 23   ›
            Avvik                    4    ›   (åpne)
            EM-frister               3    ›   (denne uka)
            Aktive prosjekter       23    ›   (uke 28)

        🔑 FORSIDEN EIES AV ANDRE — jeg leverer BARE mine tall.
        Penger kommer fra Finans, post fra Kommunikasjon, «Krever deg i dag» fra
        AI KR. Bygde jeg hele boksen, ville jeg duplisert tre spors data og skapt
        en fjerde sannhet om samme tall. Kontrakten er: hver flate leverer sitt,
        forsiden setter sammen.

        📌 «18 / 23» — teller OG nevner. Fasiten viser aldri et nakent tall her;
        «18 i rute» uten «av 23» er ikke en status, det er et tall uten målestokk.

        🛑 `avvik` returneres som False, ikke 0. Det finnes ingen avviksmodell i
        `fiq_gui_prj` ennå (`fiq.befaring.funn.type = avvik` er nærmest, og den
        eies delvis av Salg fram til `state = overfort`). **0 ville sagt «ingen
        avvik» — det er en påstand jeg ikke kan belegge.** False sier «vet ikke»,
        og forsiden kan skjule feltet i stedet for å vise en løgn.
        """
        data = self.get_prosjektoversikt(firma_id=firma_id, grense=500)
        prosjekter = data["prosjekter"]

        # «I rute» = ikke rød på noen av de to aksene. Vi bruker risiko-dommen,
        # ikke budsjett_status alene — et prosjekt med frist i dag er ikke i rute
        # selv om økonomien er sunn.
        i_rute = [
            p for p in prosjekter
            if p["risiko"] in ("i_balanse", "ferdig")
        ]

        # Lokal import: `timedelta` importeres allerede lokalt i _kolonner()
        # lenger opp. Å flytte den til toppen ville rørt en metode som ikke er
        # min sak akkurat nå — én endring om gangen.
        from datetime import timedelta

        i_dag = fields.Date.context_today(self)
        uke_slutt = i_dag + timedelta(days=(6 - i_dag.weekday()))
        frister_uka = [
            p for p in prosjekter
            if p["frist"] and i_dag <= fields.Date.to_date(p["frist"]) <= uke_slutt
        ]

        return {
            "prosjekter_i_rute": len(i_rute),
            "prosjekter_totalt": len(prosjekter),
            "aktive_prosjekter": len(prosjekter),
            "frister_denne_uka": len(frister_uka),
            # 🛑 Ikke bygget — se docstring. False, aldri 0.
            "avvik_apne": False,
            # Hva forsiden skal åpne når noen klikker et tall. Nøkkelen er slot-
            # navnet i `fiq_gui_flates` (`gui_prj`), ikke en xmlid — da bytter
            # skallet innmat og RAMMEN STÅR. Med xmlid ville doAction forlatt
            # Kontrollrommet, som er nettopp feilen vi brukte 23.07 på å finne.
            "slot": "gui_prj",
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
            # `date_deadline` er Datetime i Odoo 19 — konverter FØR bruk.
            frist_dato = t.date_deadline.date() if t.date_deadline else None
            rader.append({
                "id": t.id,
                "navn": t.display_name,
                # Oppgavenummer (code) er STABILT; WBS er dynamisk. Aldri bland dem.
                "oppgavenr": (t.code or "") if "code" in t._fields else "",
                "wbs": t.fiq_wbs_number or "",
                "ansvarlige": ", ".join(t.user_ids.mapped("name")),
                "er_ai": not bool(t.user_ids),
                "stadium": t.stage_id.display_name or "",
                "ferdig": ferdig,
                "frist": fields.Date.to_string(frist_dato) if frist_dato else False,
                # 🔴 SAMME FORM SOM get_oppgaver_over_tid. Sto tidligere som rå
                # `t.priority` («0»/«1») mens den andre utgangen ga «h»/«m» —
                # to former for samme begrep fra samme datalag. Klienten kunne
                # ikke vite hvilken den fikk, og `prioSymbol("1")` traff ingen
                # gren og falt stille til ▪. Ingen feilmelding.
                "prioritet": self._prioritet(t),
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
