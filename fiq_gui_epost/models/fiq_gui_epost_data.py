# -*- coding: utf-8 -*-
#
# Meldingssenter – data-lag (steg 1 av "native Meldingssenter").
# Leser EKTE tall fra Odoos meldingstabell (mail.message) i stedet for de
# oppdiktede tallene i V00.04-skissen. Kjører som den innloggede brukeren →
# record rules styrer synlighet (samme mønster som fiq_gui_control.get_kommunikasjon).
#
# Definisjoner (v1, dokumentert – "innboks/uleste/sendt"):
#   * sendt   = e-poster skrevet av en intern ansatt (utgående/logget av oss).
#   * innboks = ekte e-poster PÅ elementer (prosjekt/oppgave/kontakt) som IKKE er
#               internt forfattet (mottatt utenfra) = alle element-e-poster minus sendt.
#   * uleste  = meldinger som krever handling for den innloggede brukeren (Odoos
#               standard varsel-status, "needaction").
#
# Taksonomi-splitt (0–8) og paring kommer i senere steg (fiq_komm_match).

import json
import re
from datetime import timedelta

from odoo import api, fields, models

# Basisfilter: ekte kommunikasjon PÅ et element, ikke Discuss-kanaler.
# Speiler domenet i fiq_gui_control.get_kommunikasjon (verifisert mønster).
_ON_RECORD = [
    ("model", "!=", False),
    ("res_id", "!=", False),
    ("model", "not in", ["discuss.channel", "mail.channel"]),
]

_PERIOD_DAYS = {"dag": 1, "uke": 7, "maaned": 30}

# FIQ områdekart 0–8 (+ 2.90 IT, 8.50 AI) — farger fra fargekart. Count fylles av paring
# (fiq_komm_match) senere; til da stillas med 0. (navn ikke ID i dialog.)
_TAKSONOMI = [
    ("1", "1 Ledelse", "graa"),
    ("2", "2 Administrasjon", "blaa"),
    ("2.90", "2.90 IT", "lilla"),
    ("3", "3 Drift", "slate"),
    ("4", "4 Logistikk", "oransje"),
    ("5", "5 Marked", "gronn"),
    ("6", "6 Salg", "rod"),
    ("7", "7 Prosjekter", "gronn"),
    ("8", "8 FAG", "gronn"),
    ("8.50", "8.50 AI", "lilla"),
]
# Tverrgående bokser (Gjermund: «Urutet»→«Uavklart»).
_TVERRGAENDE = [
    ("viktig", "Viktig", "rod"),
    ("haster", "Haster", "crit"),
    ("uavklart", "Uavklart", "amber"),
    ("motereferater", "Møtereferater", "tealx"),
    ("reklame", "Reklame", "slate"),
]

# Standard nøkkelord per tverrgående boks (config-overstyrbart: systemparameter
# fiq_gui_epost.tverr_keywords = JSON {kode: [ord, ...]}). Treff i emne + preview.
_TVERR_KW_DEFAULT = {
    "haster": ["haster", "urgent", "asap", "snarest", "umiddelbart"],
    "viktig": ["viktig", "important", "prioritet", "high priority"],
    "motereferater": ["referat", "møtereferat", "moetereferat", "minutes of meeting", "referat fra"],
    "reklame": ["nyhetsbrev", "newsletter", "avmeld", "meld deg av", "unsubscribe",
                "kampanje", "black friday", "rabattkode"],
}
# Avsender-mønstre (email_from) som markerer reklame/automatisk post.
_REKLAME_FROM = ["noreply", "no-reply", "no_reply", "newsletter", "nyhetsbrev",
                 "marketing", "mailchimp", "sendgrid"]

_TVERR_CODES = {k for k, _, _ in _TVERRGAENDE}
_AREA_CODES = {k for k, _, _ in _TAKSONOMI}


class FiqMeldingssenterData(models.AbstractModel):
    _name = "fiq.meldingssenter.data"
    _description = "Meldingssenter – ekte tall fra mail.message"

    def _period_domain(self, period):
        """Legg på dato-avgrensning for dag/uke/maaned. 'alle' = ingen grense."""
        days = _PERIOD_DAYS.get(period)
        if days:
            return [("date", ">=", fields.Datetime.now() - timedelta(days=days))]
        return []

    @api.model
    def get_my_config(self):
        """Oppstarts-config til den native flaten: firmaer brukeren kan velge,
        gjeldende firma, presence-liste og tema. Kjøres ved onWillStart."""
        firms = [{"id": c.id, "navn": c.name,
                  "kode": c.code if "code" in c._fields else "",
                  "logo": self._logo_data(c)}
                 for c in self.env.user.company_ids]
        # «Alle» øverst (Gjermund: e-post i alle firmaer → velg alle eller spesifikk).
        firms = [{"id": False, "navn": "Alle", "kode": "∗", "logo": ""}] + firms
        return {
            "firms": firms,
            "current_firm": self.env.company.id,
            "logo": self._logo_data(self.env.company),
            "presence": self.get_presence(),
            "user": self.env.user.name,
            "theme": "system",
        }

    @staticmethod
    def _logo_data(company):
        """Firmalogo som data-URL. Bruker firmaets egen logo (res.company.logo);
        faller tilbake til Kontrollrom-logoen (fiq_control_logo) hvis satt. Tom
        streng = ingen logo → flaten viser «FIQ»-reserven."""
        logo = company.logo or (
            company.fiq_control_logo if "fiq_control_logo" in company._fields else False)
        if not logo:
            return ""
        logo = logo.decode() if isinstance(logo, bytes) else logo
        return "data:image/png;base64,%s" % logo

    @api.model
    def get_meldingssenter_data(self, firm=False, period="alle"):
        """Ekte basis-tall til Meldingssenter-flaten.

        Kjøres som brukeren → hver bruker teller kun det de har tilgang til.
        firm = firma-id (valgfri) → firma-scoping når firma-velgeren byttes i topplinja.
               Filter = mail.message.record_company_id (lagret felt = firmaet til elementet
               meldingen henger på) → bytt firma, tallene reberegnes umiddelbart.
        period = dag | uke | maaned | alle.
        Returns: {"innboks", "uleste", "sendt", "firm", "period"}
        """
        Msg = self.env["mail.message"]
        dom = self._period_domain(period)
        if firm:
            dom = dom + [("record_company_id", "=", int(firm))]

        # Alle ekte e-poster på et element (mottatt + sendt).
        epost_dom = _ON_RECORD + [("message_type", "=", "email")] + dom
        epost_totalt = Msg.search_count(epost_dom)

        # Sendt = e-poster forfattet av en intern ansatt (ikke share/portal-bruker).
        sendt = Msg.search_count(epost_dom + [("author_id.user_ids.share", "=", False)])

        # Innboks (mottatt) = alle element-e-poster minus de vi selv sendte.
        innboks = max(epost_totalt - sendt, 0)

        # Uleste = Odoos standard varsel-status for den innloggede brukeren.
        uleste = Msg.search_count([("needaction", "=", True)] + dom)

        return {
            "innboks": innboks,
            "uleste": uleste,
            "sendt": sendt,
            "firm": firm,
            "period": period,
        }

    @api.model
    def get_messages(self, boks="innboks", firm=False, period="alle", q=False, limit=80):
        """Outlook-stil meldingsliste for en boks. Ekte mail.message, kjørt som brukeren.
        boks = innboks | sendt | uleste (0–8-taksonomi krever paring, kommer med fiq_komm_match).
        Rader: {id, fra, adresse, til, emne, preview, dato, ulest, retning, model, res_id, element}."""
        Msg = self.env["mail.message"]
        dom = _ON_RECORD + [("message_type", "in", ["email", "comment"])] + self._period_domain(period)
        if firm:
            dom.append(("record_company_id", "=", int(firm)))
        if boks == "uleste":
            dom.append(("needaction", "=", True))
        elif boks == "sendt":
            dom += [("message_type", "=", "email"), ("author_id.user_ids.share", "=", False)]
        elif boks == "innboks":
            dom.append(("message_type", "=", "email"))
        elif boks in _TVERR_CODES or boks in _AREA_CODES:
            # Kategori-boks (crawl): begrens til de e-postene sorteringen la her.
            tverr_ids, omr_ids = self._classify_all(firm, period)
            src = tverr_ids if boks in _TVERR_CODES else omr_ids
            dom.append(("id", "in", list(src.get(boks, ()))))
        if q:
            dom = ["|", "|", ("subject", "ilike", q), ("email_from", "ilike", q),
                   ("record_name", "ilike", q)] + dom
        out = []
        for m in Msg.search(dom, order="date desc", limit=limit):
            internal = bool(m.author_id and m.author_id.user_ids
                            and any(not u.share for u in m.author_id.user_ids))
            # Mottakere ("Til") — kun der Odoo har løst dem (ellers tomt, ikke dikt)
            til = m.partner_ids.mapped("display_name") if m.partner_ids else []
            element = ""
            try:
                element = self.env[m.model].browse(m.res_id).display_name or ""
            except Exception:
                element = ""
            out.append({
                "id": m.id,
                "fra": m.author_id.display_name if m.author_id else (m.email_from or "—"),
                "adresse": m.email_from or "",
                "til": til,
                "emne": (m.subject or m.preview or "").strip()[:120] or "(uten emne)",
                "preview": (m.preview or "")[:140],
                "dato": m.date.strftime("%d.%m %H:%M") if m.date else "",
                "ulest": bool(m.needaction) if "needaction" in m._fields else False,
                "retning": "sendt" if internal else "mottatt",
                "model": m.model,
                "res_id": m.res_id,
                "element": element,
            })
        return out

    # ---- Crawl / sortering: legg hver e-post i riktige bokser ------------------------
    # «Crawle gjennom mailen for å vise riktig» (Gjermund): les emne + preview + avsender
    # og sorter. Tverrgående = nøkkelord/avsender (config-drevet). Områder 0–8 = via
    # elementet e-posten henger på (prosjekt/oppgave → område-kode i prosjekt-treet).

    def _tverr_keywords(self):
        raw = self.env["ir.config_parameter"].sudo().get_param("fiq_gui_epost.tverr_keywords")
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return _TVERR_KW_DEFAULT

    def _classify_tverr(self, subject, preview, email_from):
        """Hvilke tverrgående bokser matcher e-posten (multi-label)."""
        text = ("%s %s" % (subject or "", preview or "")).lower()
        frm = (email_from or "").lower()
        hits = set()
        for code, words in self._tverr_keywords().items():
            if any(w and w.lower() in text for w in words):
                hits.add(code)
        if any(p in frm for p in _REKLAME_FROM):
            hits.add("reklame")
        return hits

    def _area_index(self):
        """{prosjekt-id: område-kode} for aktive prosjekter (opp til område-nivå =
        barn av firma-rot; f.eks. «7 Prosjekter» → «7»). Defensivt."""
        P = self.env["project.project"]
        if "parent_id" not in P._fields:
            return {}
        projs = P.search([("active", "=", True)])
        parent = {p.id: (p.parent_id.id if p.parent_id else False) for p in projs}
        name = {p.id: (p.name or "") for p in projs}
        roots = set(pid for pid, par in parent.items() if not par)

        def code(pid):
            cur, hop = pid, 0
            while parent.get(cur) and parent[cur] not in roots and hop < 20:
                cur = parent[cur]
                hop += 1
            m = re.match(r"^\s*(\d+(?:\.\d+)*)\s+", name.get(cur, ""))
            return m.group(1) if m else None

        return {pid: code(pid) for pid in parent}

    def _classify_all(self, firm, period, limit=3000):
        """{boks-kode: sett av message-id} for tverrgående + område + uavklart.
        Én lettvekts-crawl over e-postene i scope."""
        Msg = self.env["mail.message"]
        dom = _ON_RECORD + [("message_type", "=", "email")] + self._period_domain(period)
        if firm:
            dom.append(("record_company_id", "=", int(firm)))
        rows = Msg.search_read(
            dom, ["id", "subject", "email_from", "model", "res_id"],
            limit=limit, order="date desc")
        area_idx = self._area_index()
        # Oppgave→prosjekt for e-post som henger på oppgaver (ett batch-søk)
        task_ids = list({r["res_id"] for r in rows
                         if r.get("model") == "project.task" and r.get("res_id")})
        task_proj = {}
        if task_ids:
            for t in self.env["project.task"].browse(task_ids).exists():
                task_proj[t.id] = t.project_id.id if t.project_id else False
        tverr = {k: set() for k, _, _ in _TVERRGAENDE}
        omr = {k: set() for k, _, _ in _TAKSONOMI}
        for r in rows:
            hits = self._classify_tverr(r.get("subject"), "", r.get("email_from"))
            area = None
            if r.get("model") == "project.project":
                area = area_idx.get(r.get("res_id"))
            elif r.get("model") == "project.task":
                area = area_idx.get(task_proj.get(r.get("res_id")))
            if area and area in omr:
                omr[area].add(r["id"])
            for h in hits:
                if h in tverr:
                    tverr[h].add(r["id"])
            if not hits and not area:
                tverr["uavklart"].add(r["id"])
        return tverr, omr

    @api.model
    def get_boxes(self, firm=False, period="alle"):
        """Bokser med EKTE tall: basis + tverrgående (crawl) + områder 0–8 (via paring).
        Farger følger fargekart. Config-drevet nøkkelord: systemparameter
        fiq_gui_epost.tverr_keywords (JSON)."""
        d = self.get_meldingssenter_data(firm=firm, period=period)
        basis = [
            {"kode": "innboks", "navn": "Innboks", "count": d["innboks"], "farge": "graa"},
            {"kode": "uleste", "navn": "Uleste", "count": d["uleste"], "farge": "amber"},
            {"kode": "sendt", "navn": "Sendt", "count": d["sendt"], "farge": "gronn"},
        ]
        tverr_ids, omr_ids = self._classify_all(firm, period)
        tverr = [{"kode": k, "navn": n, "count": len(tverr_ids.get(k, ())), "farge": f}
                 for k, n, f in _TVERRGAENDE]
        taks = [{"kode": k, "navn": n, "count": len(omr_ids.get(k, ())), "farge": f}
                for k, n, f in _TAKSONOMI]
        return {"basis": basis, "tverrgaende": tverr, "taksonomi": taks,
                "firm": firm, "period": period}

    # ---- Skriv-API: handle på en melding (tildel · arkivér · svar · presence) ----

    @api.model
    def tildel(self, message_id, user_id, deadline=False, note=False):
        """Tildel en melding til en ansvarlig med frist (leder-dirigering §C.1).
        Lager en Odoo-aktivitet (to-do) på elementet meldingen henger på → vises i
        den ansvarliges aktiviteter. Ren arbeidsdelegering, ikke innsyn i øvrig post."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m or not m.model or not m.res_id:
            return False
        todo = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        vals = {
            "res_model_id": self.env["ir.model"]._get_id(m.model),
            "res_id": m.res_id,
            "user_id": int(user_id),
            "summary": (m.subject or "Oppfølging fra Meldingssenter")[:120],
            "note": note or (m.preview or ""),
        }
        if todo:
            vals["activity_type_id"] = todo.id
        if deadline:
            vals["date_deadline"] = deadline
        return self.env["mail.activity"].create(vals).id

    @api.model
    def arkiver(self, message_id, model, res_id):
        """Arkivér en melding på et element (prosjekt/oppgave): fest innhold + vedlegg
        der den hører hjemme, sporbart. (Full PDF-render av selve e-posten kommer i v2 —
        her kopieres innhold + vedlegg til mål-elementet via message_post.)"""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return False
        target = self.env[model].browse(int(res_id)).exists()
        if not target or not hasattr(target, "message_post"):
            return False
        target.message_post(
            body=m.body or (m.preview or ""),
            subject="[Arkivert] %s" % (m.subject or ""),
            attachment_ids=m.attachment_ids.ids,
            message_type="comment",
        )
        return True

    @api.model
    def svar(self, message_id, reply_all=False):
        """Svar / Svar alle → åpner e-post-komposeren forhåndsutfylt.
        🛑 SENDER IKKE — brukeren godkjenner og sender selv (e-post ut = menneske-gate §A.7)."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return False
        partners = m.author_id
        if reply_all:
            partners |= m.partner_ids
        ctx = {
            "default_model": m.model,
            "default_res_ids": [m.res_id],
            "default_parent_id": m.id,
            "default_subject": "Re: %s" % (m.subject or ""),
            "default_composition_mode": "comment",
            "default_partner_ids": [(6, 0, partners.ids)],
        }
        return {
            "type": "ir.actions.act_window",
            "name": "Svar alle" if reply_all else "Svar",
            "res_model": "mail.compose.message",
            "view_mode": "form",
            "views": [[False, "form"]],
            "target": "new",
            "context": ctx,
        }

    @api.model
    def get_kandidater(self, message_id):
        """Koblingen (§C.3): for en e-post — finn prosjektene/oppgavene AVSENDEREN
        henger sammen med (poster der samme avsender har kommunisert før), NYESTE
        øverst. «Tok opp prosjektene mailen var del av.» Defensivt, som brukeren."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return {"prosjekt": [], "oppgave": []}
        if m.author_id:
            base = [("author_id", "=", m.author_id.id)]
        elif m.email_from:
            base = [("email_from", "=ilike", m.email_from)]
        else:
            return {"prosjekt": [], "oppgave": []}
        Msg = self.env["mail.message"]
        pros, opp, seen_p, seen_o = [], [], set(), set()
        for mm in Msg.search(base + [("model", "in", ["project.project", "project.task"]),
                                     ("res_id", "!=", False)], order="date desc", limit=200):
            try:
                rec = self.env[mm.model].browse(mm.res_id).exists()
            except Exception:
                rec = False
            if not rec:
                continue
            f = rec._fields
            if mm.model == "project.project" and rec.id not in seen_p:
                seen_p.add(rec.id)
                pros.append({"id": rec.id, "navn": rec.name or "",
                             "no": (rec.sequence_code if "sequence_code" in f else "") or ""})
            elif mm.model == "project.task" and rec.id not in seen_o:
                seen_o.add(rec.id)
                opp.append({"id": rec.id, "navn": rec.name or "",
                            "no": (rec.code if "code" in f else "") or "",
                            "prosjekt": rec.project_id.name or ""})
            if len(pros) >= 5 and len(opp) >= 5:
                break
        return {"prosjekt": pros[:5], "oppgave": opp[:5]}

    @api.model
    def get_presence(self):
        """TIL STEDE NÅ — samme robuste regnestykke som Kontrollrommet: innstempling
        (møtt på jobb) + pågående møte + online-status, ikke bare rå online-status.
        Delegerer til fiq_gui_control så «til stede» betyr det samme begge steder.
        Faller tilbake til enkel online-status hvis Kontrollrom-flaten mangler."""
        farge2status = {"green": "online", "orange": "away", "red": "offline"}
        try:
            kr = self.env["fiq.gui.control.config"].get_presence()
            return [{"id": p.get("id"), "navn": p.get("navn") or "",
                     "status": farge2status.get(p.get("farge"), "offline")}
                    for p in kr]
        except Exception:
            out = []
            for u in self.env["res.users"].search([("share", "=", False), ("active", "=", True)]):
                out.append({
                    "id": u.id, "navn": u.name,
                    "status": u.im_status if "im_status" in u._fields else "offline",
                })
            return out
