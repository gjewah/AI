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

    @api.model
    def get_ai_oppgaver(self, company_id=False):
        """Oversikt over alle AI-økter/oppgaver (Claude Code + Cowork) logget i Odoo.

        Kjøres som brukeren → tilgangsregler styrer synlighet.
        company_id (valgfri) → firma-scoping for firma-snippet.
        Returns: {root, groups[{id,no,name,done,total,tasks[...]}],
                  tot{done,pag,vent,tot,pct}, krever[...]}.
        """
        ICP = self.env["ir.config_parameter"].sudo()
        out = {"root": "", "groups": [],
               "tot": {"done": 0, "pag": 0, "vent": 0, "tot": 0, "pct": 0},
               "krever": []}
        try:
            pid = int(ICP.get_param("fiq_gui_ai_kr.okter_project_id", "0") or 0)
        except Exception:
            pid = 0
        if not pid:
            return out

        P = self.env["project.project"]
        root = P.browse(pid).exists()
        if not root:
            return out
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

    @api.model
    def get_okter(self, company_id=False, status=False):
        """Øktregisteret (D5) til AI KR-oversikten: alle Claude Code + Cowork-økter
        Claude har ført. Kjøres som brukeren. Firma-scoping for firma-snippet."""
        dom = []
        if company_id:
            dom.append(("company_id", "=", int(company_id)))
        if status:
            dom.append(("status", "=", status))
        Okt = self.env["fiq.ai.okt"]
        out = []
        for o in Okt.search(dom, order="sist_aktiv desc", limit=200):
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
            })
        return out

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
