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
                rows.append({
                    "id": t.id,
                    "no": (t.code if "code" in f else "") or "",
                    "name": t.name or "",
                    "who": "du" if t.user_ids else "ai",
                    "st": st,
                    "stage": stage.name if stage else "",
                    "over": over,
                    "frist": str(t.date_deadline)[:10] if t.date_deadline else "",
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
