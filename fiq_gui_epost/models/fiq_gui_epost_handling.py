#
# «Gjør noe med denne e-posten» — valgene som tar en melding videre.
#
# Gjermund 24.07.2026: «omgjøring til PDF og Lagre på SP og legg til lenke på
# oppgaven eller opprett oppgave eller opprett leads eller so må være med som valg».
#
# Masterspec §C.6: «Arkivér som PDF på bestemt prosjekt + oppgave → vises der
# (typisk oppgave «EL» = e-post-logg). Vedlegg arkiveres i Odoo + på prosjektet i
# SharePoint + metadata på DOKUMENT-nivå.»
#
# 🔑 SKILLET SOM STYRER FILA: en e-post er FLYKTIG — `mail.message` er delt, kan
# slettes og bærer ingen struktur. Alt her gjør den om til noe VARIG: en PDF som
# ligger fast, en oppgave med ansvarlig, et lead i salgsløpet. Det er derfor de
# hører sammen i én fil, selv om de lager ulike ting.
#
# 🛑 INGEN AV DEM SENDER NOE UT. De oppretter internt. E-post ut er menneske-gate
# (masterspec §A.7) og skjer via `svar()`, som åpner komposeren og lar mennesket
# trykke send.

import logging

from odoo import api, models
from odoo.tools import html_escape

_logger = logging.getLogger(__name__)


class FiqGuiEpostHandling(models.AbstractModel):
    """Handlinger som tar en e-post videre til noe varig."""

    _name = "fiq.meldingssenter.handling"
    _description = "Kommunikasjon – ta e-posten videre (PDF · oppgave · lead · SP)"

    # =====================================================================
    #  Felles
    # =====================================================================

    def _melding(self, message_id):
        return self.env["mail.message"].browse(int(message_id)).exists()

    def _epost_som_html(self, m):
        """Selve e-posten som en komplett HTML-side — grunnlaget for PDF-en.

        Tar med hodet (fra · til · dato · emne), ikke bare kroppen: en arkivert
        e-post uten avsender og dato er ikke dokumentasjon, bare tekst.
        """
        til = ", ".join(m.partner_ids.mapped("display_name")) if m.partner_ids else ""
        fra = (m.author_id.display_name if m.author_id else m.email_from) or "ukjent"
        naar = m.date.strftime("%d.%m.%Y %H:%M") if m.date else ""
        rader = [
            ("Fra", fra),
            ("Til", til),
            ("Dato", naar),
            ("Emne", m.subject or "(uten emne)"),
        ]
        hode = "".join(
            "<tr><td style='padding:2px 10px 2px 0;color:#666;white-space:nowrap'>"
            f"<b>{html_escape(merke)}</b></td>"
            f"<td style='padding:2px 0'>{html_escape(verdi or '')}</td></tr>"
            for merke, verdi in rader
        )
        # `m.body` er allerede sanitert HTML fra Odoo (mail.message sanitizer).
        return (
            "<html><head><meta charset='utf-8'/></head>"
            "<body style='font-family:Arial,sans-serif;font-size:12px;color:#111'>"
            f"<table style='margin-bottom:14px'>{hode}</table>"
            "<hr style='border:0;border-top:1px solid #ccc'/>"
            f"<div>{m.body or ''}</div>"
            "</body></html>"
        )

    # =====================================================================
    #  1 · E-posten som PDF
    # =====================================================================

    @api.model
    def epost_til_pdf(self, message_id, res_model=False, res_id=False):
        """Gjør SELVE E-POSTEN om til en PDF og fest den der den hører hjemme.

        Skiller seg fra `til_pdf()` i datamodellen: den konverterer et VEDLEGG,
        denne konverterer meldingen. Begge finnes fordi begge trengs — «arkivér
        e-posten» og «gjør dette vedlegget om til PDF» er to ulike ærend.

        Uten `res_model`/`res_id` festes PDF-en der meldingen allerede henger.
        """
        m = self._melding(message_id)
        if not m:
            return {"ok": False, "feil": "Meldingen finnes ikke."}

        mal = res_model or m.model
        mid = int(res_id) if res_id else m.res_id
        if not mal or not mid:
            return {
                "ok": False,
                "feil": "Velg et prosjekt eller en oppgave å arkivere den på først.",
            }
        target = self.env[mal].browse(mid).exists()
        if not target:
            return {"ok": False, "feil": "Fant ikke elementet PDF-en skulle festes på."}
        try:
            target.check_access("write")
        except Exception:
            return {
                "ok": False,
                "feil": "Du har ikke skrivetilgang til dette elementet.",
            }

        try:
            pdf = self.env["ir.actions.report"]._run_wkhtmltopdf(
                [self._epost_som_html(m)]
            )
        except Exception as e:
            _logger.warning("PDF av e-post %s feilet: %s", m.id, e)
            return {"ok": False, "feil": f"PDF-motoren feilet: {e}"}

        # Datoen FØRST i filnavnet: da sorterer arkivet seg selv kronologisk.
        dato = m.date.strftime("%Y-%m-%d") if m.date else "udatert"
        emne = (m.subject or "epost").strip()[:70]
        for tegn in '\\/:*?"<>|':
            emne = emne.replace(tegn, "-")
        vedlegg = self.env["ir.attachment"].create(
            {
                "name": f"{dato} {emne}.pdf",
                "raw": pdf,
                "mimetype": "application/pdf",
                "res_model": mal,
                "res_id": mid,
            }
        )
        if hasattr(target, "message_post"):
            target.message_post(
                body=self.env._(
                    "E-posten «%(emne)s» arkivert som PDF av %(bruker)s.",
                    emne=m.subject or "(uten emne)",
                    bruker=self.env.user.name,
                ),
                attachment_ids=[vedlegg.id],
                message_type="comment",
            )
        return {
            "ok": True,
            "id": vedlegg.id,
            "navn": vedlegg.name,
            "url": f"/web/content/{vedlegg.id}?download=true",
            "element": target.name or "",
        }

    # =====================================================================
    #  2 · Lagre på SharePoint
    # =====================================================================

    @api.model
    def sp_status(self, res_model, res_id):
        """Har dette elementet en SharePoint-mappe å lagre i?

        🛑 Flaten spør om dette FØR den viser «Lagre på SP» som et valg. En knapp
        som alltid vises og noen ganger svarer «går ikke» er samme feil som de døde
        paringsfeltene: den ser ut som en funksjon.
        """
        if not res_model or not res_id:
            return {"klar": False, "grunn": "Ingen prosjekt eller oppgave valgt."}
        rec = self.env[res_model].browse(int(res_id)).exists()
        if not rec:
            return {"klar": False, "grunn": "Fant ikke elementet."}
        if "sp_mappe_item_id" not in rec._fields:
            return {
                "klar": False,
                "grunn": "SharePoint-kobling finnes ikke på denne typen.",
            }
        if not rec.sp_mappe_item_id:
            return {
                "klar": False,
                "grunn": f"«{rec.name or ''}» har ingen SharePoint-mappe ennå. "
                "Opprett mappa på elementet først.",
                "url": "",
            }
        return {
            "klar": True,
            "url": rec.sp_mappe_url or "",
            "navn": rec.sp_mappenavn or rec.name or "",
        }

    @api.model
    def lagre_pa_sp(self, message_id, res_model, res_id):
        """Lagre e-post-PDF-en i elementets SharePoint-mappe.

        🔴 STATUS 24.07.2026: **selve opplastingen finnes ikke ennå.** Modulen
        `fiq_dokument_sp_id` bærer ID-ene (drive_id · item_id · url), men
        Graph-kallet som faktisk laster opp en fil er ikke bygget noe sted —
        verifisert ved søk over alle moduler i repoet.

        Derfor gjør denne det som FAKTISK kan gjøres nå: lager PDF-en og fester
        den i Odoo på elementet, og svarer ærlig at SP-delen venter. PDF-en er
        laget og ligger trygt; når broen kommer, er det den samme fila som skal opp.

        🛑 Alternativet — å si «lagret på SharePoint» og bare feste den i Odoo —
        ville vært den verste varianten: brukeren tror dokumentet ligger på SP,
        og oppdager det først når hun leter etter det der.
        """
        pdf = self.epost_til_pdf(message_id, res_model, res_id)
        if not pdf.get("ok"):
            return pdf
        sp = self.sp_status(res_model, res_id)
        pdf["sp_klar"] = sp.get("klar", False)
        pdf["sp_url"] = sp.get("url", "")
        pdf["sp_melding"] = (
            "PDF-en er laget og festet på elementet i Odoo. Opplasting til "
            "SharePoint er ikke koblet opp ennå — fila må inntil videre legges "
            "i mappa manuelt."
            if sp.get("klar")
            else sp.get("grunn", "")
        )
        return pdf

    # =====================================================================
    #  3 · Opprett oppgave fra e-posten
    # =====================================================================

    @api.model
    def opprett_oppgave(self, message_id, project_id, navn=False, user_id=False):
        """Lag en oppgave AV e-posten — masterspec §C.6.

        🔑 Spec-en er presis om noe som er lett å gjøre feil:
        «mailen i LOGGEN (ikke beskrivelsen)».

        Legger vi e-postteksten i beskrivelsesfeltet, blir den redigerbar og mister
        avsender og dato — den slutter å være dokumentasjon på hva som faktisk ble
        sagt. I loggen står den urørt, med hvem og når.
        """
        m = self._melding(message_id)
        if not m:
            return {"ok": False, "feil": "Meldingen finnes ikke."}
        prosjekt = self.env["project.project"].browse(int(project_id)).exists()
        if not prosjekt:
            return {"ok": False, "feil": "Velg et prosjekt oppgaven skal ligge i."}
        try:
            prosjekt.check_access("write")
        except Exception:
            return {"ok": False, "feil": "Du har ikke skrivetilgang til prosjektet."}

        vals = {
            "name": (navn or m.subject or "Oppfølging fra e-post").strip()[:200],
            "project_id": prosjekt.id,
            "company_id": prosjekt.company_id.id or self.env.company.id,
        }
        if user_id:
            vals["user_ids"] = [(6, 0, [int(user_id)])]
        oppgave = self.env["project.task"].create(vals)

        # E-posten inn i LOGGEN — hele kroppen, med hode, urørt.
        oppgave.message_post(
            body=self._epost_som_html(m),
            subject=m.subject or "",
            attachment_ids=m.attachment_ids.ids,
            message_type="comment",
        )
        # Par meldingen med den nye oppgaven, så flaten viser dem sammen.
        m.sudo().write({"model": "project.task", "res_id": oppgave.id})
        return {
            "ok": True,
            "id": oppgave.id,
            "navn": oppgave.name,
            "nummer": (oppgave.code or "") if "code" in oppgave._fields else "",
            "prosjekt": prosjekt.name or "",
        }

    # =====================================================================
    #  4 · Opprett lead / salgsmulighet
    # =====================================================================

    @api.model
    def opprett_lead(self, message_id, navn=False, user_id=False):
        """Lag en salgsmulighet av e-posten.

        Kunden hentes fra avsenderen når vi kjenner hen. Er avsenderen ukjent,
        settes `email_from` i stedet — vi oppretter ALDRI en ny kontakt her.
        En e-post er et for tynt grunnlag til å lage en kunde av; det gir dubletter
        i kunderegisteret, og det er nettopp dublett-problemet person-oversikten
        finnes for å rydde opp i.
        """
        m = self._melding(message_id)
        if not m:
            return {"ok": False, "feil": "Meldingen finnes ikke."}
        if "crm.lead" not in self.env:
            return {"ok": False, "feil": "CRM er ikke installert på denne basen."}

        vals = {
            "name": (navn or m.subject or "Ny henvendelse").strip()[:200],
            "type": "opportunity",
            "company_id": (m.record_company_id.id or self.env.company.id),
        }
        # Kjenner vi avsenderen, kobles leadet til kontakten. Gjør vi ikke det,
        # bærer leadet bare e-postadressen — vi oppretter ALDRI en ny kontakt her.
        if m.author_id:
            vals["partner_id"] = m.author_id.id
        else:
            vals["email_from"] = m.email_from or ""
        if user_id:
            vals["user_id"] = int(user_id)

        try:
            lead = self.env["crm.lead"].create(vals)
        except Exception as e:
            _logger.warning("Kunne ikke opprette lead fra melding %s: %s", m.id, e)
            return {"ok": False, "feil": f"Kunne ikke opprette salgsmuligheten: {e}"}

        lead.message_post(
            body=self._epost_som_html(m),
            subject=m.subject or "",
            attachment_ids=m.attachment_ids.ids,
            message_type="comment",
        )
        return {
            "ok": True,
            "id": lead.id,
            "navn": lead.name,
            "kunde": lead.partner_id.display_name if lead.partner_id else "",
        }

    # =====================================================================
    #  5 · Legg lenke til e-posten på et element
    # =====================================================================

    @api.model
    def legg_lenke(self, message_id, res_model, res_id):
        """Legg en LENKE til e-posten på et element — uten å flytte meldingen.

        Forskjellen fra paring: paring flytter meldingen dit, og den forsvinner fra
        der den var. Noen ganger gjelder én e-post to steder — den hører hjemme på
        prosjektet, men oppgaven trenger den også. Da er en lenke riktig svar, ikke
        en kopi og ikke en flytting.
        """
        m = self._melding(message_id)
        if not m:
            return {"ok": False, "feil": "Meldingen finnes ikke."}
        if res_model not in ("project.project", "project.task", "crm.lead"):
            return {
                "ok": False,
                "feil": "Kan bare lenke til prosjekt, oppgave eller salgsmulighet.",
            }
        target = self.env[res_model].browse(int(res_id)).exists()
        if not target:
            return {"ok": False, "feil": "Fant ikke elementet."}
        try:
            target.check_access("write")
        except Exception:
            return {"ok": False, "feil": "Du har ikke skrivetilgang til elementet."}

        # Dyplenke til meldingen der den ligger. `base_url` fra systemparam — aldri
        # hardkodet vertsnavn, det ville pekt feil på Staging kontra Production.
        base = (
            self.env["ir.config_parameter"].sudo().get_param("web.base.url") or ""
        ).rstrip("/")
        url = f"{base}/odoo/action-mail.action_view_mail_message/{m.id}"
        emne = html_escape(m.subject or "(uten emne)")
        fra = html_escape(
            (m.author_id.display_name if m.author_id else m.email_from) or "ukjent"
        )
        naar = m.date.strftime("%d.%m.%Y %H:%M") if m.date else ""
        target.message_post(
            body=self.env._(
                "E-post fra %(fra)s (%(naar)s): "
                '<a href="%(url)s">%(emne)s</a> — lenket hit av %(bruker)s.',
                fra=fra,
                naar=naar,
                url=url,
                emne=emne,
                bruker=self.env.user.name,
            ),
            message_type="comment",
        )
        return {"ok": True, "url": url, "element": target.name or ""}
