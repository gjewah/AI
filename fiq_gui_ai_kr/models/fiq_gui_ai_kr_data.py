# -*- coding: utf-8 -*-
#
# FIQ AI KR (AI Kontrollrom) – data-lag, increment 2.01: oppgave-oversikt.
# Samler ALLE AI-økter/oppgaver (Claude Code + Cowork) som er logget i Odoo, med
# 👤/🤖-merke, status og «krever handling». Bygger VIDERE på det etablerte
# get_cockpit-mønsteret i fiq_gui_control (rører den IKKE – add-only, egen modul).
#
# Config-drevet: systemparameter fiq_gui_ai_kr.okter_project_id = rot-prosjektet
# for AI-øktene (f.eks. «AI Økter (MP)»). Kan byttes uten ny modulversjon.
#
# Snippet-tanken (firma → rolle → person) styrer SENERE hvordan delene settes
# sammen; dette data-laget tar allerede et firma-filter så en firma-snippet virker.

from odoo import api, fields, models


class FiqGuiAiKrData(models.AbstractModel):
    _name = "fiq.gui.ai.kr.data"
    _description = "FIQ AI KR – data-lag (oppgave-oversikt over AI-økter)"

    # Kandidat-navn for rot-prosjektet, i prioritert rekkefølge. Første treff vinner.
    # «AI Økter (MP)» = det historisk seedede navnet. «8.50 AI (MP)» = AI-paraplyen som
    # faktisk finnes på fiqas Staging (verifisert 18.07.2026).
    OKTER_ROT_KANDIDATER = ["AI Økter (MP)", "8.50 AI (MP)", "8.50 AI"]

    # ── SAMLEBOKSER PÅ KR-FORSIDEN ──────────────────────────────────────────────
    # Gjermund 19.07.2026: «KR må egentlig være en samling av Samlebokser fra hver av de
    # forskjellige Rommene med de mest prioriterte oppgaver — om det er 5 saker som haster
    # på finans og tre i dag, vises det som en boks i KR, og trykker jeg på en av boksene
    # kommer jeg inn i finans eller RGS. Trykker jeg på PRJ haster, kommer jeg til PRJ.»
    #
    # Kravspek `kontrollrom_spec.md`: «Pulse (3 KPI + hva haster)» + «hendelser gruppert på
    # viktighet, hva haster nå». Dette er Pulse-laget realisert per FLATE.
    #
    # MEKANISMEN FINNES ALLEREDE: `get_fiq_flater()` i fiq_gui_control vet hvilke flater
    # som er registrert (ir.config_parameter). Vi spør hver av dem om ETT tall.
    #
    # KONTRAKTEN — en flate leverer sine hastesaker med én metode på sin egen modell:
    #
    #     def get_kr_boks(self, company_id=False):
    #         return {"haster": 5, "i_dag": 3, "totalt": 12,
    #                 "linjer": [{"tekst": "Faktura forfalt 45 dager", "res_id": 42}]}
    #
    # Flater UTEN metoden vises ikke — ingen tomme bokser, ingen støy. En ny modul får
    # sin boks ved å legge til metoden; ingenting her må endres.
    #
    # RO-BUDSJETT (spec: «HARDT ro-budsjett, default STILLE leseflate»): boksen viser TALL,
    # ikke varsler. Ingen popup, ingen badge som maser. Bare et tall du kan klikke på.
    KR_BOKS_METODE = "get_kr_boks"

    @api.model
    def get_kr_bokser(self, company_id=False):
        """Samle ett boks-kort per registrert flate. Klikk → åpner flaten.

        Returnerer: [{key, label, xmlid, haster, i_dag, totalt, linjer, farge}, …]
        sortert med det som haster mest øverst — det er hele poenget med forsiden.
        """
        out = []
        # 🔴 SAVEPOINT — ikke pynt. Funnet på ekte data 19.07.2026 (meldt av Finans-økta):
        # `get_fiq_flater()` i KR 6.85+ leser kolonnen `skjulte_flater`. Er KR-modulen to
        # versjoner bak i DB (6.84 installert, 6.85 i kode), kaster den en SQL-feil —
        # og PostgreSQL avbryter da HELE transaksjonen. Et bart `except Exception` fanger
        # unntaket, men transaksjonen er allerede død: alle ETTERFØLGENDE kall feiler med
        # «current transaction is aborted», også kall som ikke har noe med KR å gjøre.
        # Målt: fire urelaterte metoder falt av samme grunn.
        # `cr.savepoint()` ruller tilbake KUN dette kallet, så resten av flaten overlever.
        try:
            with self.env.cr.savepoint():
                flater = self.env["fiq.gui.control.config"].get_fiq_flater()
        except Exception:
            # KR-kjernen kan mangle (valgfri modul) ELLER være for gammel for kontrakten.
            # Begge deler betyr det samme her: ingen flater å spørre — ikke en krasj.
            return out

        for flate in flater or []:
            key = flate.get("key")
            xmlid = flate.get("xmlid")
            if not (key and xmlid):
                continue

            # Hvilken modell eier flaten? Handlingen vet det ikke alltid, så vi slår opp
            # en modell med samme «familie»-navn: fiq.gui.<key>.data er husets mønster.
            data = self._finn_boks_leverandor(key)
            if data is None:
                continue  # flaten har ingen boks å levere — vises ikke

            try:
                # Savepoint per flate: feiler ÉN flates boks i SQL (manglende kolonne,
                # utdatert modul), avbryter Postgres hele transaksjonen — og da faller
                # ALLE de andre boksene med den. Savepoint isolerer skaden til én flate.
                with self.env.cr.savepoint():
                    boks = data.get_kr_boks(company_id=company_id) or {}
            except Exception:
                # En flate som feiler skal ALDRI ta ned forsiden for de andre.
                # (Samme lærdom som blank-skjerm-fella 18.07: én modul veltet hele GUI-et.)
                continue

            haster = int(boks.get("haster") or 0)
            i_dag = int(boks.get("i_dag") or 0)
            totalt = int(boks.get("totalt") or 0)
            if not (haster or i_dag or totalt):
                continue  # ingenting å vise — ikke lag en tom boks

            out.append({
                "key": key,
                "label": flate.get("label") or key,
                "xmlid": xmlid,
                "haster": haster,
                "i_dag": i_dag,
                "totalt": totalt,
                "linjer": (boks.get("linjer") or [])[:5],  # topp 5, ikke en hel liste
                "farge": "rod" if haster else ("gul" if i_dag else "nøytral"),
            })

        # Haster øverst, så dagens, så resten. Forsiden skal svare på «hva nå?».
        out.sort(key=lambda b: (-b["haster"], -b["i_dag"], b["label"]))
        return out

    def _finn_boks_leverandor(self, key):
        """Finn modellen som kan levere boks-tall for en flate.

        Husets mønster er `fiq.gui.<key>.data` (fiq.gui.rgs.data, fiq.gui.prj.data …).
        Finnes den ikke, eller mangler den metoden, leverer flaten ingen boks — og det
        er helt greit. Ingen skal tvinges til å implementere kontrakten.
        """
        # 🔴 FUNNET PÅ EKTE DATA 19.07.2026: nøkkelen bruker UNDERSTREK («ai_kr»), mens
        # modellnavn bruker PUNKTUM («fiq.gui.ai.kr.data»). Uten oversettelsen under lette
        # koden etter «fiq.gui.ai_kr.data» — som ikke finnes — og get_kr_bokser returnerte
        # 0 bokser for ALLE flater, inkludert min egen. Flaten så ut til å virke; den var tom.
        # Nok et tilfelle av «koden kjørte, resultatet var galt».
        prikk = key.replace("_", ".")
        for navn in ("fiq.gui.%s.data" % prikk, "fiq.gui.%s.data" % key,
                     "fiq.gui.%s" % prikk, "fiq.gui.%s" % key):
            if navn in self.env and hasattr(self.env[navn], self.KR_BOKS_METODE):
                return self.env[navn]
        return None

    def _finn_okter_rot(self):
        """Finn rot-prosjektet for AI-økter på NAVN — aldri hardkodet id.

        Brukes når systemparameteren mangler (typisk etter DB-nullstilling på Staging).
        Returnerer et project.project-recordset (tomt hvis ingenting matcher).
        """
        Project = self.env["project.project"].sudo()
        for navn in self.OKTER_ROT_KANDIDATER:
            # `name` er oversettbar (jsonb) i Odoo 19 -> `=ilike` med eksakt verdi er
            # tryggere enn `=` mot et oversatt felt.
            treff = Project.search([("name", "=ilike", navn)], limit=1)
            if treff:
                return treff
        return Project.browse()

    def _stage_is_done(self, stage):
        """Ferdig-stadium = fold eller is_closed (defensivt mot feltvariasjon)."""
        if not stage:
            return False
        f = stage._fields
        if "is_closed" in f and stage.is_closed:
            return True
        if "fold" in f and stage.fold:
            return True
        return False

    def _delt_med(self, record):
        """Hvem posten er delt med = følgere som IKKE er vanlige interne brukere
        (ekstern kontakt eller portal/share-bruker). Speiler project_shared-logikken
        (Loym) for «shared», men gir NAVNENE i tillegg til ja/nei. Defensivt."""
        out = []
        partners = getattr(record, "message_partner_ids", False)
        if not partners:
            return out
        for p in partners:
            if not p.user_ids or p.user_ids.filtered(lambda u: u.share):
                out.append(p.display_name or p.name or "—")
        return out

    def _prosjekt_ferdig(self, p):
        """Prosjekt regnes som fullført/kansellert hvis stadiet er lukket/foldet eller
        stadienavnet tyder på det. Defensivt (project.project.stage varierer)."""
        stage = getattr(p, "stage_id", False)
        if not stage:
            return (False, False)
        nm = (stage.name or "").lower()
        sf = stage._fields
        lukket = ("is_closed" in sf and stage.is_closed) or ("fold" in sf and stage.fold)
        ferdig = lukket or "ferdig" in nm or "fullf" in nm or "done" in nm or "closed" in nm
        kansellert = "kansel" in nm or "avlyst" in nm or "cancel" in nm
        return (bool(ferdig), bool(kansellert))

    @api.model
    def get_ai_oppgaver(self, company_id=False, skjul_ferdig=False,
                        skjul_kansellert=False, kun_kunde=False):
        """Oversikt over alle AI-økter/oppgaver (Claude Code + Cowork) logget i Odoo.

        Kjøres som brukeren → tilgangsregler styrer synlighet.
        company_id → firma-scoping. skjul_ferdig/skjul_kansellert → fjern fullførte/
        kansellerte prosjekter. kun_kunde → bare prosjekter med kunde (partner_id).
        Returns: {root, groups[...], tot{...}, krever[...]}.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        out = {"root": "", "groups": [],
               "tot": {"done": 0, "pag": 0, "vent": 0, "tot": 0, "pct": 0},
               "krever": []}
        try:
            pid = int(ICP.get_param("fiq_gui_ai_kr.okter_project_id", "0") or 0)
        except (ValueError, TypeError):
            pid = 0

        P = self.env["project.project"]
        root = P.browse(pid).exists() if pid else False
        if not root:
            # SELVHELBREDENDE: finn rot-prosjektet på navn og lagre valget.
            #
            # Hvorfor dette trengs (målt på fiqas Staging 18.07.2026, ikke antatt):
            # parameteren ble seedet manuelt 11.07, men **staging-DB er efemer** — den ble
            # nullstilt og seedingen forsvant. Flaten returnerte da tomt («Ingen prosjekter
            # matcher filtrene») mens basen hadde 150 aktive prosjekter. Gjermund så en tom
            # flate uten å kunne vite at årsaken var en manglende parameter, ikke en ødelagt
            # flate. Manuell re-seeding ville bare utsatt problemet til neste nullstilling.
            #
            # Hooks duger ikke: `post_init_hook` kjører KUN ved install, ikke ved upgrade
            # (verifisert i Odoo 19 `odoo/modules/loading.py:239-244`) — modulen er allerede
            # installert, så en hook ville aldri kjørt. Derfor løses det her, ved oppslag.
            #
            # Aldri hardkodet id: id-er varierer per base (fiqas/sdvg/jpc01/vidir).
            root = self._finn_okter_rot()
            if not root:
                return out
            ICP.set_param("fiq_gui_ai_kr.okter_project_id", str(root.id))
        out["root"] = root.name or ""

        projects = list(root)
        if "parent_id" in P._fields:
            projects += list(P.search(
                [("parent_id", "=", root.id), ("active", "=", True)], order="id"))

        Task = self.env["project.task"]
        f = Task._fields
        today = fields.Date.context_today(self)
        stmap = {"ferdig": "done", "pagar": "pag", "venter": "vent"}

        for p in projects:
            # Prosjekt-filtre (Gjermund): skjul fullførte/kansellerte + kun kunde.
            if kun_kunde and "partner_id" in P._fields and not p.partner_id:
                continue
            if skjul_ferdig or skjul_kansellert:
                ferdig, kansellert = self._prosjekt_ferdig(p)
                if skjul_ferdig and ferdig:
                    continue
                if skjul_kansellert and kansellert:
                    continue
            dom = [("project_id", "=", p.id)]
            if company_id and "company_id" in f:
                dom.append(("company_id", "=", int(company_id)))
            tasks = Task.search(dom, order="id")
            if not tasks:
                continue
            rows, done = [], 0
            for t in tasks:
                stage = t.stage_id if "stage_id" in f and t.stage_id else False
                st = "ferdig" if self._stage_is_done(stage) else "venter"
                nm = (stage.name or "").lower() if stage else ""
                if st != "ferdig" and ("pågår" in nm or "progress" in nm or "doing" in nm):
                    st = "pagar"
                if st == "ferdig":
                    done += 1
                over = False
                try:
                    over = bool(t.date_deadline
                                and fields.Date.to_date(str(t.date_deadline)[:10]) < today)
                except Exception:
                    over = False
                delt_med = self._delt_med(t)
                rows.append({
                    "id": t.id,
                    "no": (t.code if "code" in f else "") or "",
                    "name": t.name or "",
                    "who": "du" if t.user_ids else "ai",
                    "st": st,
                    "stage": stage.name if stage else "",
                    "over": over,
                    "frist": str(t.date_deadline)[:10] if t.date_deadline else "",
                    # Åpne tilhørende element (alltid tilgjengelig fra oversikten)
                    "aapne": {"model": "project.task", "id": t.id},
                    # Delt-visning (project_shared/Loym): flagg + HVEM den er delt med
                    "delt": bool(t.shared) if "shared" in f else bool(delt_med),
                    "delt_med": delt_med,
                })
                out["tot"]["tot"] += 1
                out["tot"][stmap[st]] += 1
            out["groups"].append({
                "id": p.id,
                "no": (p.sequence_code if "sequence_code" in P._fields else "") or "",
                "name": p.name or "",
                "done": done, "total": len(rows), "tasks": rows,
            })

        mine = [r for g in out["groups"] for r in g["tasks"]
                if r["who"] == "du" and r["st"] != "ferdig"]
        mine.sort(key=lambda r: (not r["over"], r["no"]))
        out["krever"] = mine[:5]
        tot = out["tot"]
        tot["pct"] = int(round(tot["done"] * 100.0 / tot["tot"])) if tot["tot"] else 0
        return out

    # En økt som ikke har meldt seg på så lenge er sannsynligvis død, ikke aktiv.
    # Gjermund 19.07.2026: «Jeg ser ikke på dette som økter men som prosjekter og det er
    # den tullete økt-opplegget til Claude som skaper kaoset.» Registeret må derfor si
    # ÆRLIG hva som faktisk lever — en «aktiv» økt som sist meldte seg i går er en løgn
    # som gjør at han tror noe er under arbeid når det står stille.
    STILLE_TIMER = 3

    @api.model
    def get_spor(self, company_id=False):
        """Prosjektsporene til AI KR-flaten — den varige enheten.

        Gjermund 19.07.2026: «Jeg ser ikke paa dette som oekter men som PROSJEKTER.»
        Sporene er derfor det foerste han skal se, ikke oektene.
        """
        dom = []
        if company_id:
            dom.append(("company_id", "=", int(company_id)))
        out = []
        Spor = self.env["fiq.ai.spor"]
        for s in Spor.search(dom, order="kode"):
            out.append({
                "id": s.id,
                "kode": s.kode or "",
                "navn": s.name or "",
                "versjon": s.versjon or "",
                "modul": s.modul or "",
                "i_odoo": bool(s.modul_installert),
                "modul_versjon": s.modul_versjon or "",
                "status": s.status or "",
                "aktive": s.aktive_okter,
                "okter": s.antall_okter,
                "beskrivelse": s.beskrivelse or "",
                # UTEN EIER: ingen aktive oekter og status planlagt = hullet skal SYNES.
                "uten_eier": bool(s.status == "planlagt" and not s.aktive_okter),
                # HJEMLOEST: oppsamlingssporet for oekter som aldri meldte tilhoerighet.
                # Skal alltid vaere TOMT. Er det ikke det, mangler noen en eier — og da
                # skal flaten lyse roedt, ikke tie. (Gjermund 20.07: mykt krav, valg 2.)
                "hjemlost": bool(s.kode == Spor.HJEMLOS_KODE),
                "krever_opprydding": bool(s.kode == Spor.HJEMLOS_KODE and s.antall_okter),
            })
        return out

    @api.model
    def get_okter(self, company_id=False, status=False):
        """Øktregisteret (D5) til AI KR-oversikten: alle Claude Code + Cowork-økter
        Claude har ført. Kjøres som brukeren. Firma-scoping for firma-snippet.

        Hver økt får `alder` (menneskelig: «12 min», «3 t», «2 d») og `stille` (bool).
        Uten det kan man ikke skille en økt som JOBBER fra en som har stoppet opp — og
        det er nettopp den forskjellen som gjør registeret verdt å ha.
        """
        dom = []
        if company_id:
            dom.append(("company_id", "=", int(company_id)))
        if status:
            dom.append(("status", "=", status))
        Okt = self.env["fiq.ai.okt"]
        naa = fields.Datetime.now()
        out = []
        for o in Okt.search(dom, order="sist_aktiv desc", limit=200):
            minutter = None
            if o.sist_aktiv:
                minutter = int((naa - o.sist_aktiv).total_seconds() // 60)
            out.append({
                "id": o.id,
                "navn": o.name or "",
                "ref": o.okt_ref or "",
                "kilde": o.kilde or "",
                "firma": o.company_id.display_name if o.company_id else "",
                "status": o.status or "",
                "oppgave": o.task_id.display_name if o.task_id else "",
                "sammendrag": o.sammendrag or "",
                "sist_aktiv": o.sist_aktiv.strftime("%d.%m %H:%M") if o.sist_aktiv else "",
                "minutter": minutter,
                "alder": self._alder_tekst(minutter),
                # STILLE = meldte seg som aktiv, men har ikke gitt lyd fra seg siden.
                "stille": bool(
                    o.status == "aktiv" and minutter is not None
                    and minutter > self.STILLE_TIMER * 60
                ),
            })
        return out

    def _alder_tekst(self, minutter):
        """«12 min» / «3 t» / «2 d» — menneskelig, ikke et tidsstempel å regne på."""
        if minutter is None:
            return ""
        if minutter < 1:
            return "nå"
        if minutter < 60:
            return "%d min" % minutter
        if minutter < 60 * 24:
            return "%d t" % (minutter // 60)
        return "%d d" % (minutter // (60 * 24))

    @api.model
    def get_kr_boks(self, company_id=False):
        """AI KRs EGEN samleboks — samme kontrakt som alle andre flater leverer.

        AI KR skal ikke være unntaket som bare viser andres bokser. «Haster» her =
        økter som har stoppet opp uten å melde fra, for det er dem Gjermund må gripe inn i.
        """
        okter = self.get_okter(company_id=company_id)
        stille = [o for o in okter if o.get("stille")]
        aktive = [o for o in okter if o.get("status") == "aktiv"]
        return {
            "haster": len(stille),
            "i_dag": len(aktive) - len(stille),
            "totalt": len(aktive),
            "linjer": [
                {"tekst": "%s — stille i %s" % (o["navn"], o["alder"]), "res_id": o["id"]}
                for o in stille[:5]
            ],
        }

    @api.model
    def get_org(self, company_id=False):
        """Org-kart-data (AI KR D6): AI-rollene (Leder/Rådgiver) gruppert per firma,
        med Rådgiver-koblinger — grunnlag for org-kart-visningen. Feature-detektert på
        fiq.ai.rolle (degraderer pent om Rolle-modulen ikke er installert)."""
        if "fiq.ai.rolle" not in self.env:
            return {"roller": [], "installert": False}
        dom = [("aktiv", "=", True)]
        if company_id:
            dom.append(("company_id", "in", [int(company_id), False]))
        roller = []
        for r in self.env["fiq.ai.rolle"].search(dom, order="omraade_kode, name"):
            roller.append({
                "id": r.id,
                "navn": r.name or "",
                "type": r.rolletype or "",
                "omraade": r.omraade_kode or "",
                "firma": r.company_id.display_name if r.company_id else "(generisk)",
                "skill": r.skill_ref or "",
                "radgivere": r.radgivere_ids.mapped("name"),
                "ansvarlig": r.ansvarlig_id.display_name if r.ansvarlig_id else "",
            })
        return {"roller": roller, "installert": True}

    @api.model
    def get_oppgave_detalj(self, task_id):
        """Detalj for én oppgave (AI KR D3): beskrivelse · konsekvenser · ansvarlig ·
        sjekkliste · kommunikasjonshistorikk · svar-kobling. Gjenbruker mønsteret fra
        Prosjekt KR (get_detaljer) + Meldingssenter (get_kommunikasjon) — AI KR = kombinasjon
        av de to. Kjøres som brukeren. 🛑 KUN-LESENDE på oppgavenavn/-nummer (D4: aldri døpe om)."""
        Task = self.env["project.task"]
        t = Task.browse(int(task_id)).exists()
        if not t:
            return {}
        f = Task._fields

        ansvarlig = ", ".join(t.user_ids.mapped("name")) if t.user_ids else ""

        # Konsekvenser — feature-detektert felt (varierer per kunde-modul).
        konsekvens = ""
        for cand in ("konsekvens", "konsekvenser", "x_konsekvens", "consequence"):
            if cand in f and t[cand]:
                konsekvens = t[cand]
                break

        # Sjekkliste — feature-detektert one2many m/ 'checklist' i feltnavnet
        # (fiq_project_checklist); degraderer pent om modulen ikke er der.
        sjekkliste = []
        for fname, fld in f.items():
            if "checklist" in fname and getattr(fld, "type", "") == "one2many":
                for line in t[fname]:
                    lf = line._fields
                    navn = (line.name if "name" in lf else False) or line.display_name or ""
                    utfort = False
                    for dcand in ("done", "is_done", "checked"):
                        if dcand in lf:
                            utfort = bool(line[dcand])
                            break
                    sjekkliste.append({"navn": navn, "utfort": utfort})
                break

        # Kommunikasjonshistorikk på oppgaven (mail.message) — Meldingssenter-mønster.
        Msg = self.env["mail.message"]
        msgs = Msg.search([
            ("model", "=", "project.task"), ("res_id", "=", t.id),
            ("message_type", "in", ["email", "comment"]),
        ], order="date desc", limit=50)
        komm = []
        for m in msgs:
            internal = bool(
                m.author_id and m.author_id.user_ids
                and any(not u.share for u in m.author_id.user_ids)
            )
            komm.append({
                "id": m.id,
                "fra": m.author_id.display_name if m.author_id else (m.email_from or "—"),
                "retning": "sendt" if internal else "mottatt",
                "emne": (m.subject or m.preview or "").strip()[:120],
                "dato": m.date.strftime("%d.%m %H:%M") if m.date else "",
                "er_epost": m.message_type == "email",
            })

        return {
            "id": t.id,
            "navn": t.name or "",          # KUN lesing — aldri endret (D4)
            "no": (t.code if "code" in f else "") or "",
            "beskrivelse": t.description or "",
            "ansvarlig": ansvarlig,
            "konsekvenser": konsekvens,
            "sjekkliste": sjekkliste,
            "kommunikasjon": komm,
            "kan_svare": True,            # front-end åpner komposer på message_id (svar/svar alle)
            "aapne": {"model": "project.task", "id": t.id},
        }

    # ════════════════════════════════════════════════════════════════════════
    # KONKLUSJONS-LOGGEN — det Gjermund skal kunne lese OG STOPPE
    # ════════════════════════════════════════════════════════════════════════
    @api.model
    def get_konklusjoner(self, company_id=False, vis_alle=False, grense=100):
        """Konklusjonene Gjermund skal se — IKKE alle 25 483 linjene.

        Gjermunds avgrensning 20.07: «kanon + alt som er antatt eller uverifisert».
        Verifiserte smaadetaljer ingen bygger paa blir i md-filene med lenke.
        «Alt» ville gitt stoey; «kun kanon» ville skjult de smaa avgjoerelsene som
        viste seg aa vaere feil — `spor_kode=False` var ALDRI kanon.

        `vis_alle=True` naar han vil se ogsaa de verifiserte.
        """
        K = self.env["fiq.ai.konklusjon"]
        dom = []
        if company_id:
            dom.append(("company_id", "=", int(company_id)))
        if not vis_alle:
            # kanon ELLER usikker ELLER umerket ELLER bestridt (bestridte skjules aldri)
            dom += ["|", "|", "|",
                    ("er_kanon", "=", True),
                    ("sikkerhet", "in", ["antatt", "uverifisert"]),
                    ("uten_grunnlag", "=", True),
                    ("status", "=", "bestridt")]

        ut = []
        for k in K.search(dom, limit=int(grense)):
            ut.append({
                "id": k.id,
                "konklusjon": k.name or "",
                "grunnlag": k.grunnlag or "",
                "sikkerhet": k.sikkerhet or "",
                "sikkerhet_tekst": dict(K.SIKKERHET).get(k.sikkerhet, "Ikke merket"),
                "er_kanon": k.er_kanon,
                "uten_grunnlag": k.uten_grunnlag,
                "status": k.status,
                "bestridt": k.status == "bestridt",
                "bestridelse": k.bestridelse or "",
                "spor": (k.spor_id.kode or k.spor_id.name) if k.spor_id else "",
                "okt": k.okt_id.name if k.okt_id else "",
                "task_id": k.task_id.id or False,
                "oppgave": k.task_id.display_name if k.task_id else "",
                "kilde": k.kilde or "",
                "skrevet": k.skrevet.strftime("%d.%m %H:%M") if k.skrevet else "",
            })
        return ut

    @api.model
    def get_konklusjon_puls(self, company_id=False):
        """Tallene oeverst: hvor mye krever Gjermund, hvor mye gaar av seg selv."""
        K = self.env["fiq.ai.konklusjon"]
        dom = [("company_id", "=", int(company_id))] if company_id else []
        return {
            "bestridt": K.search_count(dom + [("status", "=", "bestridt")]),
            "uten_grunnlag": K.search_count(dom + [("uten_grunnlag", "=", True)]),
            "usikre": K.search_count(dom + [("sikkerhet", "in", ["antatt", "uverifisert"]),
                                            ("status", "!=", "bestridt")]),
            "kanon": K.search_count(dom + [("er_kanon", "=", True)]),
            "totalt": K.search_count(dom),
        }

    @api.model
    def bestrid_konklusjon(self, konklusjon_id, begrunnelse=False):
        """🛑 NOEDBREMSEN. Virker UTEN begrunnelse — det er hele poenget.

        Gjermund 21.07: «av og til maa jeg bruke ordet feil for aa faa stoppet oekter
        som har glemt regelen om kunstpause og starter aa bygge paa feil konklusjon».
        Krevde vi en begrunnelse, ville stoppen ventet paa at han rekker aa formulere
        seg — mens oekta bygger videre. Begrunnelsen kan komme etterpaa.
        """
        k = self.env["fiq.ai.konklusjon"].browse(int(konklusjon_id)).exists()
        if not k:
            return {"ok": False, "feil": "Konklusjonen finnes ikke."}
        k.check_access("write")          # aldri stoppe noe i et firma du ikke ser
        k.bestrid(begrunnelse)
        return {"ok": True, "status": k.status}

    @api.model
    def spor_om_konklusjon(self, konklusjon_id, tekst):
        """Spoer uten aa stoppe — mellomtingen mellom «la staa» og noedbremsen."""
        k = self.env["fiq.ai.konklusjon"].browse(int(konklusjon_id)).exists()
        if not k:
            return {"ok": False, "feil": "Konklusjonen finnes ikke."}
        k.check_access("write")
        k.sporsmaal(tekst)
        return {"ok": True}

    # ════════════════════════════════════════════════════════════════════════
    # GODKJENNINGSKOEEN — det som fjerner klikkingen fra Gjermunds hverdag
    # Gjermund 22.07: «Jeg rekker knapt gjoere annet enn aa trykke ALLOW hvert
    # tredje til hvert femte sekund.» Fasit: artifact 13184ec2.
    # ════════════════════════════════════════════════════════════════════════
    @api.model
    def get_godkjenninger(self, company_id=False, vis_besvarte=False, grense=50):
        """Koeen Gjermund svarer i. Ubesvart oeverst, deretter det som haster."""
        G = self.env["fiq.ai.godkjenning"]
        dom = []
        if company_id:
            dom.append(("company_id", "=", int(company_id)))
        if not vis_besvarte:
            dom.append(("svar", "=", False))

        # To knapperader — fasiten har begge. Samme koe, ulike ord.
        KNAPPER = {
            "godkjenning": [
                {"valg": "godkjent", "tekst": "🟢 Godkjent", "farge": "g"},
                {"valg": "ja_men", "tekst": "🟠 Ja, men…", "farge": "o", "krever_tekst": True},
                {"valg": "nei", "tekst": "🔴 Nei", "farge": "r"},
                {"valg": "alltid", "tekst": "🟢⭐ Alltid", "farge": "s"},
            ],
            "oppgave": [
                {"valg": "jeg_gjor", "tekst": "🟢 Jeg gjør det", "farge": "g"},
                {"valg": "senere", "tekst": "🟠 Senere", "farge": "o"},
                {"valg": "dropp", "tekst": "🔴 Dropp", "farge": "r"},
            ],
        }
        MERKE = {"ai": "🤖 AI-økt", "menneske": "👤 Menneske-gate", "klokke": "👤 Klokke-oppgave"}

        ut = []
        for g in G.search(dom, limit=int(grense)):
            ut.append({
                "id": g.id,
                "sporsmaal": g.name or "",
                "detalj": g.detalj or "",
                "kilde": g.kilde,
                "kilde_tekst": MERKE.get(g.kilde, ""),
                "haster": g.haster,
                "svar": g.svar or "",
                "forbehold": g.forbehold or "",
                "besvart": bool(g.svar),
                "knapper": KNAPPER.get(g.art, KNAPPER["godkjenning"]),
                "spor": (g.spor_id.kode or g.spor_id.name) if g.spor_id else "",
                "okt": g.okt_id.name if g.okt_id else "",
                "task_id": g.task_id.id or False,
                # 🔑 «Alltid» er bare aerlig hvis den faktisk kan huske noe.
                # Uten noekkel ville knappen lovet mer enn den holder.
                "kan_alltid": bool(g.noekkel),
                "firma": g.company_id.display_name if g.company_id else "",
                "alder": self._alder(g.opprettet) if g.opprettet else "",
            })
        return ut

    @api.model
    def svar_godkjenning(self, godkjenning_id, valg, forbehold=False):
        """Gjermund trykker en knapp. «Alltid» lagres som staaende regel."""
        g = self.env["fiq.ai.godkjenning"].browse(int(godkjenning_id)).exists()
        if not g:
            return {"ok": False, "feil": "Spørsmålet finnes ikke."}
        g.check_access("write")     # aldri svare i et firma du ikke ser
        g.svar_paa(valg, forbehold)
        return {"ok": True, "svar": g.svar}

    @api.model
    def get_staaende_regler(self, company_id=False):
        """«Alltid»-svarene, saa Gjermund kan se og trekke tilbake.

        En staaende regel han ikke finner igjen, er en regel han ikke kontrollerer.
        """
        return self.env["fiq.ai.godkjenning"].staaende_regler(company_id)

    @api.model
    def trekk_tilbake_regel(self, noekkel, company_id=False):
        return {"ok": self.env["fiq.ai.godkjenning"].trekk_tilbake(noekkel, company_id)}

    def _alder(self, naar):
        """«12 min» · «3 t» · «2 d» — menneskelig, ikke tidsstempel."""
        if not naar:
            return ""
        d = fields.Datetime.now() - naar
        m = int(d.total_seconds() // 60)
        if m < 1:
            return "nå"
        if m < 60:
            return "%d min" % m
        if m < 1440:
            return "%d t" % (m // 60)
        return "%d d" % (m // 1440)
