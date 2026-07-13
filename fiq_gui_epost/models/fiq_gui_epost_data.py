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
        Comp = self.env["res.company"]
        firms = [{"id": c.id, "navn": c.name,
                  "kode": c.code if "code" in c._fields else ""}
                 for c in self.env.user.company_ids]
        return {
            "firms": firms,
            "current_firm": self.env.company.id,
            "presence": self.get_presence(),
            "user": self.env.user.name,
            "theme": "system",
        }

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

    @api.model
    def get_boxes(self, firm=False, period="alle"):
        """Bokser til Meldingssenter-flaten: basis (ekte tall NÅ) + tverrgående + 0–8-taksonomi
        (stillas — count 0 til fiq_komm_match-paring finnes). Dynamisk: front-end skjuler count=0
        der det gir mening. Farger følger fargekart. Config-drevet mål: fiq.msg.box (senere)."""
        d = self.get_meldingssenter_data(firm=firm, period=period)
        basis = [
            {"kode": "innboks", "navn": "Innboks", "count": d["innboks"], "farge": "graa"},
            {"kode": "uleste", "navn": "Uleste", "count": d["uleste"], "farge": "amber"},
            {"kode": "sendt", "navn": "Sendt", "count": d["sendt"], "farge": "gronn"},
        ]
        tverr = [{"kode": k, "navn": n, "count": 0, "farge": f, "trenger_paring": True}
                 for k, n, f in _TVERRGAENDE]
        taks = [{"kode": k, "navn": n, "count": 0, "farge": f, "trenger_paring": True}
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
    def get_presence(self):
        """TIL STEDE NÅ: interne brukere med online-status (im_status). Grovkornet
        (online/away/offline); samtykke/opt-in styres i innstillinger (§12)."""
        out = []
        for u in self.env["res.users"].search([("share", "=", False), ("active", "=", True)]):
            out.append({
                "id": u.id,
                "navn": u.name,
                "status": u.im_status if "im_status" in u._fields else "offline",
            })
        return out
