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
# FARGEKART per HOVEDområde. Undergrupper arver forelderens farge (unntak under).
#
# KILDE: lest direkte fra områdeikonene i SDVp-mediebiblioteket
# («051 SDVp/2 ADMIN/2.90 IT/2.90 IT/051 2.90 IT - 05 MedieBibl», 41 ikoner),
# + Gjermunds korreksjoner 18.07.2026 der ikonene manglet farge eller ikke skilte:
#   0 Info  → grå                    (ikon er gråtone)
#   1 LED   → SOM 2.70, mørk blå     (ikon er gråtone)
#   3 DRIFT → knall grønn            (ikon er gråtone)
#   5 MAR   → mørk kraftig grønn  ┐  ikonene ga BEGGE #548430 — måtte skilles,
#   7 PRJ   → lysere grønn        ┘  ellers blir boksene like
#   8 FAG   → grønn/blå (teal)       (ikon er gul — overstyrt)
_AREA_FARGE = {
    "0": "graa",        # Info
    "1": "blaam",       # Ledelse — samme som 2.70
    "2": "blaa",        # Administrasjon (lys blå #0078CC)
    "3": "gronnk",      # Drift — knall grønn
    "4": "oransje",     # Logistikk (#E47830)
    "5": "gronnm",      # Marked — mørk kraftig grønn
    "6": "rod",         # Salg (#D80000)
    "7": "gronnl",      # Prosjekter — lysere grønn
    "8": "tealx",       # FAG — grønn/blå
    "9": "turkis",      # Privat (#78D8D8)
}
# UNNTAK: underområder med EGEN farge — arver IKKE hovedområdets.
# Verifisert mot ikonene i mediebiblioteket (lest fra pikslene, ikke antatt).
_AREA_FARGE_UNNTAK = {
    # Finans under Admin — mørk blå #243C6C (ikon-verifisert)
    "2.70": "blaam",    # BPA / FIi
    "2.71": "blaam",    # FIe
    "2.80": "blaam",    # RGS
    # IT-familien — lilla #7830A8 (ikon-verifisert). AI hører hit, ikke til gul 8-serie.
    "2.90": "lilla",    # IT
    "2.91": "lilla",    # ERP
    "8.50": "lilla",    # AI
    "8.51": "lilla",    # AID
}
# 8.50–8.99 er AI-serien og skal være lilla som 2.90 IT (Gjermund 18.07.2026),
# selv om 8 FAG ellers er grønn/blå. Håndteres i _omraade_farge().
_AI_SERIE = re.compile(r"^8\.(5\d|[6-9]\d)$")


def _omraade_farge(kode):
    """Farge for en områdekode.

    Rekkefølge: eksakt unntak → AI-serien 8.50–8.99 (lilla) → hovedområdets farge.
    Undergrupper arver altså forelderen med mindre de står i unntakslista.
    """
    kode = (kode or "").strip()
    if kode in _AREA_FARGE_UNNTAK:
        return _AREA_FARGE_UNNTAK[kode]
    if _AI_SERIE.match(kode):
        return "lilla"                       # hele AI-serien, som 2.90 IT
    return _AREA_FARGE.get(kode.split(".")[0], "graa")

# Reserve hvis prosjekt-treet ikke er lesbart (tom base / manglende rettigheter).
# Den LEVENDE taksonomien leses fra treet — se _taksonomi_levende().
_TAKSONOMI = [
    ("1", "1 Ledelse", "graa"),
    ("2", "2 Administrasjon", "blaa"),
    ("3", "3 Drift", "slate"),
    ("4", "4 Logistikk", "oransje"),
    ("5", "5 Marked", "gronn"),
    ("6", "6 Salg", "rod"),
    ("7", "7 Prosjekter", "gronn"),
    ("8", "8 FAG", "gronn"),
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

    # ---- 000-RETTIGHET: kryss-firma-innsyn er en RETTIGHET, ikke en visnings-innstilling ----
    # Kanon: docs/0.00 IQ kanon_000_rettighet_presence_epost_UTKAST_01.md (Gjermund 2026-07-16).
    # Scope hentes fra SESJONEN — ALDRI som parameter fra klienten/LLM. Fail-closed.

    def _har_000_rettighet(self):
        """Har den innloggede 000-rettighet (plattform-nivå → kryss-firma-innsyn)?

        Mekanismen er AVKLART (Gjermund 17.07.2026): 000 = egen sikkerhetsgruppe
        (`fiq_gui_control.group_000_kryss_firma`), håndhevet av Odoo — ikke av GUI-koden.
        Vi spør KR-kjernens felles hjelper (Økt 02, KR v6.76) og eier ALDRI regelen selv.
        Fail-closed: alt annet enn et utvetydig JA betyr nei.
        """
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "har_000_rettighet"):
            try:
                return bool(self.env[KR].har_000_rettighet())
            except Exception:
                return False                            # fail-closed ved feil
        return False

    def _tillatte_firmaer(self):
        """Firmaene brukeren lovlig kan se post fra. Delegerer til KR-kjernens felles
        `tillatte_firmaer()` (Økt 02) — regelen skal finnes ÉTT sted, ikke kopieres.
        Fail-closed til eget firma hvis kjernen mangler."""
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "tillatte_firmaer"):
            try:
                return self.env[KR].tillatte_firmaer() or self.env.company.ids
            except Exception:
                return self.env.company.ids
        return self.env.company.ids

    def _firma_domene(self, firm=False):
        """Firma-avgrensning på meldinger. Delegerer til KR-kjernens felles
        `firma_domene()` (Økt 02) — vårt felt er `record_company_id` (firmaet til
        elementet meldingen henger på). Klientens `firm` kan bare SNEVRE INN i det
        brukeren allerede har lov til; «Alle» = de tillatte firmaene, ALDRI ufiltrert.
        Fail-closed til eget firma hvis kjernen mangler."""
        KR = "fiq.gui.control.config"
        if KR in self.env and hasattr(self.env[KR], "firma_domene"):
            try:
                # inkluder_uten_firma: KR sjekker 000-rettigheten SELV inne i metoden —
                # ikke send vår egen sjekk inn, da får vi to oppslag som kan divergere.
                return self.env[KR].firma_domene(firm=firm, felt="record_company_id")
            except Exception:
                pass                                    # fail-closed under
        return [("record_company_id", "in", self.env.company.ids)]

    @api.model
    def get_my_config(self):
        """Oppstarts-config til den native flaten: firmaer brukeren kan velge,
        gjeldende firma, presence-liste og tema. Kjøres ved onWillStart."""
        # 000-KANON: firmavelgeren er et FILTER, ikke en tilgangsmekanisme. Den viser kun
        # firmaer brukeren FAKTISK har rett til å se post fra (sesjons-utledet, fail-closed).
        kryss = self._har_000_rettighet()
        tillatte = self._tillatte_firmaer()
        firms = [{"id": c.id, "navn": c.name,
                  "kode": c.code if "code" in c._fields else "",
                  "logo": self._logo_data(c)}
                 for c in self.env["res.company"].browse(tillatte).exists()]
        # «Alle» tilbys KUN med 000-rettighet — uten den gir «alle» null ekstra innsyn.
        if kryss and len(firms) > 1:
            firms = [{"id": False, "navn": "Alle", "kode": "∗", "logo": ""}] + firms
        return {
            "firms": firms,
            "current_firm": self.env.company.id,
            "logo": self._logo_data(self.env.company),
            "presence": self.get_presence(),
            "user": self.env.user.name,
            "kryss_firma": kryss,          # flaten kan vise at man er på plattform-nivå
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
        dom = self._period_domain(period) + self._firma_domene(firm)

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
        dom = (_ON_RECORD + [("message_type", "in", ["email", "comment"])]
               + self._period_domain(period) + self._firma_domene(firm))
        if boks == "uleste":
            dom.append(("needaction", "=", True))
        elif boks == "sendt":
            dom += [("message_type", "=", "email"), ("author_id.user_ids.share", "=", False)]
        elif boks == "innboks":
            dom.append(("message_type", "=", "email"))
        elif boks in _TVERR_CODES or re.match(r"^\d+(\.\d+)*$", str(boks) or ""):
            # Kategori-boks (crawl): begrens til de e-postene sorteringen la her.
            # Områdekoder telles på alle nivåer, så «2» gir ALT under 2 (inkl. 2.61 …).
            tverr_ids, omr_ids = self._classify_all(firm, period)
            src = tverr_ids if boks in _TVERR_CODES else omr_ids
            dom.append(("id", "in", list(src.get(boks, ()))))
        if q:
            dom = ["|", "|", ("subject", "ilike", q), ("email_from", "ilike", q),
                   ("record_name", "ilike", q)] + dom
        msgs = Msg.search(dom, order="date desc", limit=limit)
        status_map = self._status_map(msgs.ids)
        out = []
        for m in msgs:
            internal = bool(m.author_id and m.author_id.user_ids
                            and any(not u.share for u in m.author_id.user_ids))
            # Mottakere ("Til") — kun der Odoo har løst dem (ellers tomt, ikke dikt)
            til = m.partner_ids.mapped("display_name") if m.partner_ids else []
            element = ""
            try:
                # Vis prosjektnavnet som SharePoint-MAPPENAVNET (Gjermund 18.07.2026).
                # display_name gir «25_040 - 012 FIQ (MP)» (sekvensnr foran) — SP-mappa
                # heter «012 FIQ (MP)». Bruk `name` der modellen har det; ellers display_name.
                rec = self.env[m.model].browse(m.res_id)
                element = (rec.name if "name" in rec._fields else rec.display_name) or ""
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
                # 000-KANON krav 2: tydelig firmakode per melding i samlet visning
                "firma": m.record_company_id.name if m.record_company_id else "",
                "firmakode": (m.record_company_id.code
                              if m.record_company_id and "code" in m.record_company_id._fields
                              else "") or "",
                "status": status_map.get(m.id, ""),
                "status_navn": self._STATUS_NAVN.get(status_map.get(m.id), ""),
                "risiko": self._risiko(m.subject, m.email_from, m.preview),
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
        """{prosjekt-id: område-kode} — koden fra prosjektet SELV der det har en
        (f.eks. «2.61 FUe (MP)» → «2.61»), ellers arvet fra nærmeste forelder med kode.
        Gir FULL dybde: en e-post på «2.61 Loym Cooperation Agreement» havner på 2.61,
        ikke bare på «2». Defensivt."""
        P = self.env["project.project"]
        if "parent_id" not in P._fields:
            return {}
        projs = P.search([("active", "=", True)])
        parent = {p.id: (p.parent_id.id if p.parent_id else False) for p in projs}
        name = {p.id: (p.name or "") for p in projs}

        def egen_kode(pid):
            m = re.match(r"^\s*(\d+(?:\.\d+)*)", name.get(pid, ""))
            return m.group(1) if m else None

        def kode(pid):
            cur, hop = pid, 0
            while cur and hop < 20:
                k = egen_kode(cur)
                if k:
                    return k
                cur = parent.get(cur)
                hop += 1
            return None

        return {pid: kode(pid) for pid in parent}

    def _taksonomi_levende(self):
        """DYNAMISK taksonomi lest fra prosjekt-treet — ikke en hardkodet liste.
        Gjermund 08.07.2026 (masterspec §C.4): «vis KUN bokser som faktisk har innhold …
        tomme bokser skjules». Og 18.07.2026: undergrupper må kunne vises (2 Adm har
        2.05 JUR · 2.30 HMS · 2.40 KS · 2.50 KH · 2.60 FUi · 2.61 FUe …).

        Returnerer {kode: {navn, farge, nivaa, forelder}} for ALLE koder som finnes i
        treet. Hvilke som VISES avgjøres av om de har innhold (se get_boxes)."""
        P = self.env["project.project"]
        ut = {}
        for p in P.search([("active", "=", True)]):
            navn = (p.name or "").strip()
            m = re.match(r"^\s*(\d+(?:\.\d+)*)\s*(.*)$", navn)
            if not m:
                continue
            kode, rest = m.group(1), (m.group(2) or "").strip()
            # Rydd bort mal-/kopimerking og (MP) — boksen skal vise fagnavnet
            for skrot in ("(TEMPLATE)", "(COPY)", "(MAL)", "(MP)"):
                rest = rest.replace(skrot, "").strip()
            # Flere prosjekter deler samme kode: «2.61 FUe (MP)» er FAGOMRÅDET, mens
            # «2.61 Loym Cooperation Agreement» er ett enkeltprosjekt under det. Boksen
            # skal hete fagområdet → foretrekk (MP)-prosjektet, ellers korteste navn.
            er_mp = "(MP)" in navn
            if kode in ut:
                if not er_mp and (ut[kode]["er_mp"] or len(rest) >= len(ut[kode]["rest"])):
                    continue
            ut[kode] = {
                "navn": ("%s %s" % (kode, rest)).strip() if rest else kode,
                "farge": _omraade_farge(kode),
                "nivaa": kode.count("."),                  # 0 = hovedområde, 1 = undergruppe …
                "forelder": kode.rsplit(".", 1)[0] if "." in kode else False,
                "er_mp": er_mp, "rest": rest,
            }
        for v in ut.values():                              # interne hjelpefelt ut
            v.pop("er_mp", None); v.pop("rest", None)
        return ut

    def _classify_all(self, firm, period, limit=3000):
        """{boks-kode: sett av message-id} for tverrgående + område + uavklart.
        Én lettvekts-crawl over e-postene i scope."""
        Msg = self.env["mail.message"]
        dom = (_ON_RECORD + [("message_type", "=", "email")]
               + self._period_domain(period) + self._firma_domene(firm))
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
        omr = {}                                    # dynamisk: kun koder som får treff
        for r in rows:
            hits = self._classify_tverr(r.get("subject"), "", r.get("email_from"))
            area = None
            if r.get("model") == "project.project":
                area = area_idx.get(r.get("res_id"))
            elif r.get("model") == "project.task":
                area = area_idx.get(task_proj.get(r.get("res_id")))
            if area:
                # Tell på ALLE nivåer: «2.61» teller også på «2». Da viser hovedboksen
                # summen, og undergruppene sine egne tall — uten dobbelttelling i hver boks.
                deler = area.split(".")
                for i in range(len(deler)):
                    kode = ".".join(deler[:i + 1])
                    omr.setdefault(kode, set()).add(r["id"])
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

        # DYNAMISKE områdebokser (masterspec §C.4): KUN koder som faktisk har post.
        # Taksonomien leses fra prosjekt-treet → undergrupper (2.05 JUR, 2.61 FUe …)
        # kommer med av seg selv når de får innhold. Ingen hardkodet liste, ingen 0-bokser.
        levende = self._taksonomi_levende()
        reserve = {k: {"navn": n, "farge": f, "nivaa": 0, "forelder": False}
                   for k, n, f in _TAKSONOMI}
        taks = []
        for kode, ids in omr_ids.items():
            if not ids:
                continue                                   # tom = vises ikke
            meta = levende.get(kode) or reserve.get(kode) or {
                "navn": kode, "farge": _omraade_farge(kode),
                "nivaa": kode.count("."), "forelder": kode.rsplit(".", 1)[0] if "." in kode else False}
            taks.append({
                "kode": kode, "navn": meta["navn"], "count": len(ids),
                "farge": meta["farge"], "nivaa": meta["nivaa"], "forelder": meta["forelder"],
            })
        # Sorter som taksonomien leses: 1, 2, 2.05, 2.30, 2.61, 3 …
        taks.sort(key=lambda b: [int(x) if x.isdigit() else 0 for x in b["kode"].split(".")])
        return {"basis": basis, "tverrgaende": tverr, "taksonomi": taks,
                "firm": firm, "period": period}

    # ---- Paring: søk etter mål (prosjekt · oppgave · ansvarlig) ----
    #
    # Gjermund 18.07.2026 (skjermbilde): paringsfeltene Prosjekt/Oppgave/Ansvarlig/Frist var
    # rene input-felt UTEN funksjon — de så ut som et skjema, men gjorde ingenting. AI-forslagene
    # over dem («Hører sannsynligvis til») virket; den MANUELLE veien manglet helt. Når AI ikke
    # treffer, må mennesket kunne søke selv — ellers er paringen en blindvei.
    #
    # Søket er defensivt: det kjører som brukeren (record rules gjelder) OG snevres til firmaene
    # brukeren lovlig ser (`_tillatte_firmaer`). Ingen kryss-tenant-lekkasje via et søkefelt.

    @api.model
    def sok_mal(self, term, slag="prosjekt", firm=False, limit=10):
        """Søk etter paringsmål mens brukeren skriver. `slag`: prosjekt|oppgave|ansvarlig.

        Søker på BÅDE nummer og navn — Gjermund oppgir ofte prosjektnr., ikke navn
        («Prosjektnr eller navn» står i feltet). Tomt søk gir tom liste, ikke hele basen.
        """
        term = (term or "").strip()
        if not term:
            return []
        firmaer = self._tillatte_firmaer()
        if firm:                                   # klientvalg kan kun SNEVRE INN
            try:
                f = int(firm)
                firmaer = [f] if f in firmaer else firmaer
            except (TypeError, ValueError):
                pass
        ut = []
        if slag == "ansvarlig":
            dom = [("share", "=", False), ("name", "ilike", term)]
            for u in self.env["res.users"].search(dom, limit=int(limit)):
                ut.append({"id": u.id, "navn": u.name or "", "no": ""})
            return ut

        model = "project.task" if slag == "oppgave" else "project.project"
        Rec = self.env[model]
        f = Rec._fields
        # Nummerfeltet heter ulikt: prosjekt = sequence_code, oppgave = code.
        nrfelt = "code" if (slag == "oppgave" and "code" in f) else (
            "sequence_code" if "sequence_code" in f else False)
        dom = ["|", ("name", "ilike", term)] if nrfelt else [("name", "ilike", term)]
        if nrfelt:
            dom.append((nrfelt, "ilike", term))
        if "company_id" in f:
            dom.append(("company_id", "in", firmaer))
        for rec in Rec.search(dom, limit=int(limit), order="write_date desc"):
            ut.append({
                "id": rec.id,
                "navn": rec.name or "",
                "no": (rec[nrfelt] or "") if nrfelt else "",
            })
        return ut

    @api.model
    def par_melding(self, message_id, model, res_id):
        """PAR en melding med et element: flytt den dit den hører hjemme.

        Dette er selve kjernen Gjermund har bedt om — «pare riktig e-post med riktig hendelse».
        `tildel()` lager kun en aktivitet på elementet meldingen ALLEREDE henger på; den kan ikke
        flytte en upart melding. Derfor denne.

        Vi setter `model`/`res_id` på meldingen (paringen) i stedet for å kopiere innholdet —
        `arkiver()` kopierer, og to kopier av samme e-post på ett element er verre enn ingen.
        Sporbarhet: en linje i elementets chatter forteller hvem som paret og når.
        """
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m or model not in ("project.project", "project.task"):
            return False
        target = self.env[model].browse(int(res_id)).exists()
        if not target:
            return False
        # Sjekk at brukeren FAKTISK har tilgang til målet — ellers kan en id-gjetning
        # pare en melding inn i et firma brukeren ikke ser.
        try:
            target.check_access("write")
        except Exception:
            return False
        m.sudo().write({"model": model, "res_id": target.id})
        if hasattr(target, "message_post"):
            target.message_post(
                body="Melding paret hit fra Kommunikasjon av %s: %s" % (
                    self.env.user.name, m.subject or "(uten emne)"),
                message_type="comment",
            )
        return {"id": target.id, "navn": target.name or "", "model": model}

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
        # 000-KANON krav 4: svaret ARVER meldingens avsender-firma — ikke plattformen.
        # Svarer du på en Vidir-melding, går den fra Vidir. Plattformen er ingen bakvei.
        if m.record_company_id:
            ctx["allowed_company_ids"] = [m.record_company_id.id]
            ctx["force_company"] = m.record_company_id.id
            ctx["default_company_id"] = m.record_company_id.id
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

    # ---- V00.05: arbeidsstatus + internt notat + risiko-flagg ------------------------
    _STATUS_NAVN = {"apen": "Åpen", "pagar": "Pågår", "ferdig": "Ferdig"}

    # Konservativ phishing-/risiko-heuristikk (v1 — oppgraderes til AI-klassifisering).
    _RISIKO_PAY = ["bekreft betaling", "verify your account", "confirm payment",
                   "passord utløper", "kontoen din er sperret", "klikk her innen",
                   "frigi forsendel", "oppdater betalingskort", "reset your password"]
    _RISIKO_DOM = [".info", ".xyz", ".top", "-secure", "verify-", "account-", "-verify"]

    def _risiko(self, subject, email_from, body=""):
        """Enkelt risiko-signal for en innkommende e-post. Konservativ: 'hoy' kun ved
        tydelig svindel-mønster (betalings-/konto-press + mistenkelig avsender), ellers ''."""
        text = ("%s %s" % (subject or "", body or "")).lower()
        frm = (email_from or "").lower()
        pay = any(w in text for w in self._RISIKO_PAY)
        susp = any(d in frm for d in self._RISIKO_DOM)
        if pay and susp:
            return "hoy"
        return ""

    def _status_map(self, message_ids):
        """{message_id: status} for de meldingene som har fått en arbeidsstatus."""
        if not message_ids:
            return {}
        recs = self.env["fiq.meldingssenter.state"].search(
            [("message_id", "in", list(message_ids))])
        return {r.message_id.id: r.status for r in recs}

    def _melding_firma(self, message_id):
        """000-KANON krav 5: arbeidsstatus/notat skal bære MELDINGENS firma — ikke brukerens
        aktive firma. Ellers havner en 040-melding i 012s taksonomi."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        return m.record_company_id.id if (m and m.record_company_id) else self.env.company.id

    @api.model
    def set_status(self, message_id, status):
        """Sett arbeidsstatus (åpen/pågår/ferdig) på en melding. Upsert per melding."""
        if status not in self._STATUS_NAVN:
            return False
        S = self.env["fiq.meldingssenter.state"]
        rec = S.search([("message_id", "=", int(message_id))], limit=1)
        if rec:
            rec.status = status
        else:
            S.create({"message_id": int(message_id), "status": status,
                      "company_id": self._melding_firma(message_id)})
        return True

    @api.model
    def add_note(self, message_id, body):
        """Legg til et internt notat (team-only, usynlig for avsender) på en melding."""
        body = (body or "").strip()
        if not body:
            return False
        note = self.env["fiq.meldingssenter.note"].create(
            {"message_id": int(message_id), "body": body,
             "company_id": self._melding_firma(message_id)})
        return {"navn": note.user_id.name or "", "body": note.body,
                "dato": note.create_date.strftime("%d.%m %H:%M") if note.create_date else ""}

    @api.model
    def get_thread(self, message_id):
        """Lese-panel-tilstand for en melding: arbeidsstatus + interne notater (nyeste øverst)."""
        mid = int(message_id)
        S = self.env["fiq.meldingssenter.state"].search([("message_id", "=", mid)], limit=1)
        notes = self.env["fiq.meldingssenter.note"].search([("message_id", "=", mid)])
        return {
            "status": S.status if S else "",
            "notater": [{
                "navn": n.user_id.name or "",
                "body": n.body or "",
                "dato": n.create_date.strftime("%d.%m %H:%M") if n.create_date else "",
            } for n in notes],
        }

    # ---- V00.05: person-visning (klikk «Til stede» → person) + relasjoner (§C.2) -----
    @api.model
    def get_person(self, partner_id=False, user_id=False):
        """Person-kort: e-post + tilknyttede personer (§C.2) + siste hos oss + ukesplan.
        Åpnes fra «Til stede»-navnene (user_id) eller en meldings avsender (partner_id)."""
        partner = False
        if partner_id:
            partner = self.env["res.partner"].browse(int(partner_id)).exists()
        elif user_id:
            u = self.env["res.users"].browse(int(user_id)).exists()
            partner = u.partner_id if u else False
        if not partner:
            return {}
        Rel = self.env["fiq.partner.relation"]
        rtlabels = dict(Rel._fields["relation_type"].selection)
        rels = []
        for r in Rel.search(["|", ("partner_id", "=", partner.id),
                             ("related_partner_id", "=", partner.id)]):
            other = r.related_partner_id if r.partner_id.id == partner.id else r.partner_id
            rels.append({"id": other.id, "navn": other.display_name or "",
                         "type": r.relation_type, "type_navn": rtlabels.get(r.relation_type, "")})
        return {
            "id": partner.id,
            "navn": partner.display_name or "",
            "epost": partner.email or "",
            "relasjoner": rels,
            "siste": self._siste_for_partner(partner),
            "ukesplan": self._ukesplan_for_partner(partner),
        }

    def _siste_for_partner(self, partner):
        """«Siste hos oss»: nyeste salg/oppgaver/helpdesk knyttet til kontakten. Defensivt."""
        out = []
        if "crm.lead" in self.env:
            for l in self.env["crm.lead"].search(
                    [("partner_id", "=", partner.id)], order="write_date desc", limit=3):
                out.append({"type": "salg", "navn": l.name or "",
                            "dato": l.write_date.strftime("%d.%m") if l.write_date else ""})
        for t in self.env["project.task"].search(
                [("partner_id", "=", partner.id)], order="write_date desc", limit=3):
            out.append({"type": "opg", "navn": t.name or "",
                        "dato": t.write_date.strftime("%d.%m") if t.write_date else ""})
        if "helpdesk.ticket" in self.env:
            for h in self.env["helpdesk.ticket"].search(
                    [("partner_id", "=", partner.id)], order="write_date desc", limit=3):
                out.append({"type": "hd", "navn": h.name or "",
                            "dato": h.write_date.strftime("%d.%m") if h.write_date else ""})
        return out[:6]

    def _ukesplan_for_partner(self, partner):
        """Ukesplan denne uka: kalender-hendelser kontakten deltar på + oppgavefrister for
        tilknyttet bruker. (v1 — kan senere delegere til Prosjekt-modulen [[gui-naming]].)"""
        today = fields.Date.context_today(self)
        start = today - timedelta(days=today.weekday())          # mandag denne uka
        end = start + timedelta(days=6)
        out = []
        Cal = self.env["calendar.event"]
        for e in Cal.search([("partner_ids", "in", partner.id),
                             ("start", ">=", start), ("start", "<=", end)],
                            order="start", limit=30):
            out.append({"type": "kal", "navn": e.name or "",
                        "dato": e.start.strftime("%a %d.%m") if e.start else ""})
        users = partner.user_ids
        if users:
            for t in self.env["project.task"].search(
                    [("user_ids", "in", users.ids),
                     ("date_deadline", ">=", start), ("date_deadline", "<=", end)],
                    order="date_deadline", limit=30):
                out.append({"type": "opg", "navn": t.name or "",
                            "dato": t.date_deadline.strftime("%a %d.%m") if t.date_deadline else ""})
        return out

    # ---- V00.05.4: nøyaktige Fra/Til/Kopi-felter + «hvem treffer Svar alle» ----------
    @staticmethod
    def _adr_liste(rå):
        """Splitt en rå adresse-streng («A <a@x.no>, b@y.no») til en ren liste."""
        if not rå:
            return []
        return [d.strip() for d in re.split(r"[,;]", rå) if d.strip()]

    @staticmethod
    def _partner_linje(partners):
        """[{navn, adresse}] for et partner-sett — navn OG adresse (navn ikke ID)."""
        return [{"navn": p.display_name or "", "adresse": p.email or ""} for p in partners]

    @api.model
    def get_hoder(self, message_id):
        """Nøyaktige e-posthoder for lesepanelet: Fra · Til · Kopi · Blindkopi · Svar-til,
        med både navn og adresse. Viser også HVEM et «Svar alle» faktisk treffer, slik at
        konsekvensen er synlig FØR man trykker (Gjermund 2026-07-16)."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return {}
        f = m._fields
        fra = {"navn": m.author_id.display_name if m.author_id else "",
               "adresse": m.email_from or ""}
        # Til: rå adresser fra e-posten (innkommende/utgående) + koblede kontakter
        raa_til = []
        if "incoming_email_to" in f and m.incoming_email_to:
            raa_til = self._adr_liste(m.incoming_email_to)
        elif "outgoing_email_to" in f and m.outgoing_email_to:
            raa_til = self._adr_liste(m.outgoing_email_to)
        til = self._partner_linje(m.partner_ids)
        # Kopi: rå CC-adresser + koblede CC-kontakter
        raa_kopi = self._adr_liste(m.incoming_email_cc) if "incoming_email_cc" in f else []
        kopi = self._partner_linje(m.recipient_cc_ids) if "recipient_cc_ids" in f else []
        blindkopi = self._partner_linje(m.recipient_bcc_ids) if "recipient_bcc_ids" in f else []
        # «Svar alle» treffer: avsender + alle mottakere (samme som svar(reply_all=True))
        svar_alle = self._partner_linje(m.author_id | m.partner_ids)
        return {
            "fra": fra,
            "til": til, "raa_til": raa_til,
            "kopi": kopi, "raa_kopi": raa_kopi,
            "blindkopi": blindkopi,
            "svar_til": (m.reply_to or "") if "reply_to" in f else "",
            "svar_alle": svar_alle,
            "svar_kun": self._partner_linje(m.author_id),
        }

    # ---- V00.05 lag 4: vedlegg → element (Loym) + rutingregler ------------------------
    @api.model
    def get_vedlegg(self, message_id):
        """Vedleggene på en e-post (til «lagre på element»-kortet i lesepanelet)."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return []
        return [{"id": a.id, "navn": a.name or "",
                 "kb": int(round((a.file_size or 0) / 1024.0))}
                for a in m.attachment_ids]

    @api.model
    def lagre_paa_element(self, message_id, model, res_id):
        """Loym-modellen: lagre e-postens VEDLEGG på elementet meldingen gjelder
        (prosjekt/salg/helpdesk) → blir en del av Documents DER, sporbart.
        Generisk Documents-lagring skjer kun når meldingen ikke er paret til et element."""
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m or not m.attachment_ids:
            return False
        target = self.env[model].browse(int(res_id)).exists()
        if not target or not hasattr(target, "message_post"):
            return False
        target.message_post(
            body="Vedlegg fra e-post: %s" % (m.subject or ""),
            attachment_ids=m.attachment_ids.ids,
            message_type="comment", subtype_xmlid="mail.mt_note")
        return len(m.attachment_ids)

    @api.model
    def kjor_regler(self, firm=False, period="uke", limit=500):
        """Kjør aktive rutingregler over e-post i scope: sett arbeidsstatus på treff.
        Audit: oppdaterer «sist kjørt» + «treff» per regel. Config-drevet ([[feedback-config-driven]])."""
        regler = self.env["fiq.komm.regel"].search([("active", "=", True)])
        if not regler:
            return {"regler": 0, "treff": 0}
        Msg = self.env["mail.message"]
        dom = (_ON_RECORD + [("message_type", "=", "email")]
               + self._period_domain(period) + self._firma_domene(firm))
        rows = Msg.search_read(
            dom, ["id", "subject", "email_from", "preview", "record_name"],
            limit=limit, order="date desc")
        getters = {
            "avsender": lambda r: (r.get("email_from") or ""),
            "emne": lambda r: (r.get("subject") or ""),
            "innhold": lambda r: (r.get("preview") or ""),
            "element": lambda r: (r.get("record_name") or ""),
        }
        status_av_handling = {"status_apen": "apen", "status_pagar": "pagar",
                              "status_ferdig": "ferdig"}
        total = 0
        for regel in regler:
            getter = getters.get(regel.felt, getters["emne"])
            v = (regel.verdi or "").lower()
            status = status_av_handling.get(regel.handling)
            n = 0
            for r in rows:
                fv = getter(r).lower()
                match = (v in fv) if regel.operator == "inneholder" else (v == fv)
                if match:
                    if status:
                        self.set_status(r["id"], status)
                    n += 1
            regel.sist_kjort = fields.Datetime.now()
            regel.treff = (regel.treff or 0) + n
            total += n
        return {"regler": len(regler), "treff": total}

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
