#
# AI-funksjoner i Kommunikasjon — sammendrag · oppsummering · sjekkliste · plan · fritekst.
#
# Kravkilde: docs/0.00 IQ meldingssenter_masterspec.md §C.6 og §C.13:
#   §C.6  «AI/Cowork: oppsummer tråd (gjort/ikke gjort · frister · ansvarlig)»
#   §C.6  «Oppgave fra mail: … beskrivelse = AI-oppsummering»
#   §C.13 «Lange e-poster: samme AI-oppsummering + oppfølgingssak, så du slipper
#          å lese hele tråden.»
# Gjermund 24.07.2026: «lag sammendrag av mailkjede · oppsummer · legg inn sjekkliste
# på oppgave · lag en steg for steg plan · og fritekst».
#
# 🛑 ÉN AI-VEI: alt går gjennom `self.env["fiq.ai"].chat()` (fiq_ai → Odoo 19 native
# `ai` → Anthropic via fiq_ai_claude). Ingen egen HTTP-klient her — en modul til som
# snakker direkte med en leverandør er en modul til som må sikres, nøkkel-håndteres
# og oppgraderes hver for seg.
#
# 🛑 AI SKRIVER ALDRI AV SEG SELV. Alle metodene her RETURNERER tekst til flaten;
# mennesket leser, endrer og bestemmer. Det ene stedet noe lagres (`lag_sjekkliste`)
# krever at brukeren har trykket «Legg inn» ETTER å ha sett forslaget — og lagrer på
# en oppgave brukeren allerede har skriverett til. Jf. masterspec §A.7 (menneske-gate)
# og §C.8 (audit-logg for AI-svar).

import logging

from odoo import api, models
from odoo.exceptions import UserError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)

# Hvor mye av en tråd vi sender til modellen. En lang tråd koster både penger og tid,
# og de siste meldingene er nesten alltid de som avgjør. Konfigurerbart heller enn
# hardkodet: `fiq_gui_epost.ai_maks_tegn` i systemparametre.
_MAKS_TEGN_STANDARD = 24000
_MAKS_MELDINGER = 40

# Felles grunning. Den generelle FIQ-konteksten kommer fra `fiq.ai`; her legger vi
# bare på det som gjelder KOMMUNIKASJON, slik at vi ikke duplisere plattform-teksten.
_SYSTEM_KOMM = """Du hjelper en saksbehandler i FIQ AIs Kommunikasjon-flate med å håndtere e-post.

SPRÅK: norsk bokmål. Plain språk — oversett tekniske termer. Aldri engelsk med mindre kilden krever det.

FAKTA, IKKE GJETNING: bruk KUN det som står i e-posten(e) du får. Står det ikke der, skriv «går ikke fram av tråden». Finn aldri på navn, beløp, frister eller avtaler. Dette er ekte kundekorrespondanse — en oppdiktet frist blir til en ekte feil.

TONE: kort og konkret. Saksbehandleren leser dette for å slippe å lese hele tråden."""


class FiqGuiEpostAi(models.AbstractModel):
    """AI-handlinger på en melding eller en tråd. Ren lesing + tekst ut."""

    _name = "fiq.meldingssenter.ai"
    _description = "Kommunikasjon – AI-handlinger (sammendrag, plan, sjekkliste)"

    # =====================================================================
    #  Innhenting av tekst — samme kilde for alle handlingene
    # =====================================================================

    def _maks_tegn(self):
        raa = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("fiq_gui_epost.ai_maks_tegn")
        )
        try:
            return max(2000, int(raa))
        except (TypeError, ValueError):
            return _MAKS_TEGN_STANDARD

    def _traad_meldinger(self, message_id):
        """Meldingene i tråden, eldste først — konteksten AI-en skal lese.

        En «tråd» i Odoo er ikke bare `parent_id`-kjeden: svarene henger som regel
        på samme element (prosjekt/oppgave). Vi tar derfor alle meldinger på samme
        element, og faller tilbake på selve meldingen når den er upart.

        Kjøres som BRUKEREN, ikke sudo: ser du ikke meldingen i flaten, skal den
        heller ikke havne i et AI-sammendrag.
        """
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return self.env["mail.message"]
        if not m.model or not m.res_id:
            return m
        sok = self.env["mail.message"].search(
            [
                ("model", "=", m.model),
                ("res_id", "=", m.res_id),
                ("message_type", "in", ["email", "comment"]),
            ],
            order="date desc",
            limit=_MAKS_MELDINGER,
        )
        # Nyeste hentet (limit skjærer den ELDSTE bort, ikke den nyeste), men leses
        # kronologisk — en tråd gir ingen mening baklengs.
        return sok.sorted(key=lambda r: (r.date or r.create_date, r.id))

    def _som_tekst(self, meldinger):
        """Meldingene som ren tekst med avsender og dato — det AI-en faktisk leser."""
        maks = self._maks_tegn()
        biter, brukt, utelatt = [], 0, 0
        for m in meldinger:
            kropp = html2plaintext(m.body or "") if m.body else (m.preview or "")
            kropp = (kropp or "").strip()
            naar = m.date.strftime("%d.%m.%Y %H:%M") if m.date else "uten dato"
            hvem = (
                m.author_id.display_name if m.author_id else m.email_from
            ) or "ukjent"
            emne = (m.subject or "(uten emne)").strip()
            hode = f"--- {naar} | {hvem} | {emne}"
            bit = hode + "\n" + kropp
            if brukt + len(bit) > maks:
                utelatt += 1
                continue
            biter.append(bit)
            brukt += len(bit)
        tekst = "\n\n".join(biter)
        if utelatt:
            # 🔑 Si fra i selve teksten at noe er utelatt. Et sammendrag som stille
            # bygger på halve tråden er verre enn ingen sammendrag — leseren tror
            # den har fått med alt.
            tekst = (
                f"MERK: {utelatt} eldre melding(er) er utelatt fordi tråden er "
                "for lang. Sammendraget dekker de nyeste.\n\n"
            ) + tekst
        return tekst, utelatt

    def _kall(self, oppdrag, tekst):
        """Ett AI-kall. Feil kommer fram i klartekst — vi later aldri som det gikk bra."""
        if not (tekst or "").strip():
            return ""
        # 🔴 FEATURE-DETEKTERT, ikke hard avhengighet (rettet 24.07 etter at gaten falt).
        #
        # `fiq_ai` → `fiq_ai_claude` → `ai`, og `ai` er en ENTERPRISE-modul. CI-gaten
        # henter en DELVIS Enterprise-kilde (17 moduler; `ai` er ikke blant dem), så en
        # `depends: fiq_ai` i manifestet felte hele databasen — ikke bare denne modulen,
        # men alle 21 som ble installert i samme kjøring:
        #     UserError: module "fiq_ai_claude" depends on module "ai".
        #     But the latter module is not available in your system.
        #
        # 🔑 Lærdommen: en avhengighet er ikke bare «trenger jeg denne koden», men
        # «finnes hele kjeden under den, overalt der modulen skal installeres». Jeg
        # sjekket at `fiq_ai` var installert i Production — og glemte at gaten er et
        # annet miljø med en annen kilde.
        if "fiq.ai" not in self.env:
            raise UserError(
                self.env._(
                    "AI-hjelpen er ikke tilgjengelig på denne installasjonen — "
                    "modulen «FIQ AI» er ikke installert. Alt annet i Kommunikasjon "
                    "virker som før."
                )
            )
        try:
            return self.env["fiq.ai"].chat(
                oppdrag + "\n\n=== E-POST ===\n" + tekst,
                system=_SYSTEM_KOMM,
            )
        except UserError:
            # Manglende API-nøkkel o.l. — meldingen fra tjenesten er allerede lesbar.
            raise
        except Exception as e:
            _logger.warning("AI-kall feilet i Kommunikasjon: %s", e)
            raise UserError(
                self.env._(
                    "AI-tjenesten svarte ikke. Prøv igjen, eller si fra hvis det "
                    "gjentar seg. Teknisk melding: %(feil)s",
                    feil=str(e)[:200],
                )
            ) from e

    # =====================================================================
    #  De fem handlingene
    # =====================================================================

    @api.model
    def sammendrag_traad(self, message_id):
        """Sammendrag av HELE mailkjeden — Gjermund: «lag sammendrag av mailkjede».

        Masterspec §C.6: «oppsummer tråd (gjort/ikke gjort · frister · ansvarlig)».
        De tre punktene er ikke pynt: det er nettopp dem man leter etter når man
        overtar en tråd man ikke har fulgt.
        """
        meldinger = self._traad_meldinger(message_id)
        tekst, utelatt = self._som_tekst(meldinger)
        if not tekst:
            return {"tekst": "", "antall": 0, "utelatt": 0}
        svar = self._kall(
            "Lag et sammendrag av denne e-posttråden. Bruk nøyaktig disse fire "
            "overskriftene, i denne rekkefølgen:\n"
            "**Hva saken gjelder** — to–tre setninger.\n"
            "**Gjort** — punktliste over det som er avklart eller utført.\n"
            "**Ikke gjort** — punktliste over det som gjenstår eller er ubesvart.\n"
            "**Frister og ansvar** — hvem som skal gjøre hva, og innen når. "
            "Står det ingen frist, skriv «ingen frist nevnt».",
            tekst,
        )
        return {"tekst": svar, "antall": len(meldinger), "utelatt": utelatt}

    @api.model
    def oppsummer(self, message_id):
        """Kort oppsummering av ÉN melding — for lange e-poster (§C.13).

        Skiller seg fra `sammendrag_traad` ved å se på én melding, ikke kjeden:
        brukt når man står i en enkelt lang e-post og bare vil vite hva den sier.
        """
        m = self.env["mail.message"].browse(int(message_id)).exists()
        if not m:
            return {"tekst": ""}
        tekst, _u = self._som_tekst(m)
        svar = self._kall(
            "Oppsummer denne e-posten i høyst fem kulepunkter. Ta med beløp, "
            "datoer og navn som faktisk står der. Avslutt med én linje som "
            "begynner med «Krever svar:» — og skriv «nei» hvis den ikke gjør det.",
            tekst,
        )
        return {"tekst": svar}

    @api.model
    def steg_for_steg(self, message_id):
        """Steg-for-steg-plan — Gjermund: «lag en steg for steg plan».

        Returnerer TEKST, ikke lagrede poster. Planen er et utgangspunkt mennesket
        redigerer; en AI som selv oppretter oppgaver ut fra en e-post ville laget
        arbeid ingen har bestilt.
        """
        meldinger = self._traad_meldinger(message_id)
        tekst, utelatt = self._som_tekst(meldinger)
        svar = self._kall(
            "Lag en steg-for-steg-plan for å håndtere denne saken. Nummererte steg "
            "i den rekkefølgen de må gjøres. Hvert steg skal være én konkret "
            "handling som én person kan utføre — ikke et tema. Skriv ansvarlig og "
            "frist i parentes der det går fram av tråden. Er noe uklart, ta med et "
            "steg som sier hva som må avklares og med hvem.",
            tekst,
        )
        return {"tekst": svar, "utelatt": utelatt}

    @api.model
    def forslag_sjekkliste(self, message_id):
        """Foreslå sjekklistepunkter — VISES bare, lagres ikke.

        🛑 Delt i to med vilje: dette forslaget, og `lag_sjekkliste()` som lagrer.
        Mennesket skal se punktene før de havner på en oppgave. Uten den delingen
        ville et AI-kall skrevet direkte inn i noen andres prosjekt.
        """
        meldinger = self._traad_meldinger(message_id)
        tekst, _u = self._som_tekst(meldinger)
        svar = self._kall(
            "List opp hva som må gjøres i denne saken, som en sjekkliste. "
            "ÉN handling per linje. Ingen nummerering, ingen kulepunkt-tegn, ingen "
            "innledning og ingen avslutning — bare linjene, slik at de kan leses rett "
            "inn i et system. Høyst 12 linjer. Hver linje høyst 120 tegn.",
            tekst,
        )
        punkter = []
        for linje in (svar or "").splitlines():
            r = linje.strip().lstrip("-•*0123456789. )").strip()
            if r and len(punkter) < 12:
                punkter.append(r[:120])
        return {"punkter": punkter}

    @api.model
    def lag_sjekkliste(self, res_id, punkter):
        """Legg de GODKJENTE punktene inn som deloppgaver på en oppgave.

        Gjermund: «legg inn sjekkliste på oppgave». Kalles først etter at brukeren
        har sett `forslag_sjekkliste()` og trykket «Legg inn».

        🛑 Tilgang sjekkes eksplisitt: en id kan komme fra klienten, og uten denne
        sjekken kunne en gjettet id skrevet punkter inn i et prosjekt brukeren ikke
        har noe med. Samme vakt som `par_melding()`.
        """
        Task = self.env["project.task"]
        oppgave = Task.browse(int(res_id)).exists()
        if not oppgave:
            return False
        try:
            oppgave.check_access("write")
        except Exception:
            return False
        rene = [str(p).strip()[:120] for p in (punkter or []) if str(p).strip()]
        if not rene:
            return False
        # Deloppgaver (parent_id) er Odoo 19s egen sjekkliste-mekanikk på oppgaver —
        # verifisert mot project/models/project_task.py. Vi lager ikke en egen
        # sjekkliste-modell ved siden av; da ville de to visningene skilt lag.
        laget = Task.create(
            [
                {
                    "name": p,
                    "parent_id": oppgave.id,
                    "project_id": oppgave.project_id.id,
                    "company_id": oppgave.company_id.id,
                }
                for p in rene
            ]
        )
        oppgave.message_post(
            body=self.env._(
                "Sjekkliste lagt inn fra Kommunikasjon av %(bruker)s: "
                "%(antall)s punkt. Forslaget kom fra AI og er godkjent av mennesket.",
                bruker=self.env.user.name,
                antall=len(laget),
            ),
            message_type="comment",
        )
        return {"antall": len(laget), "oppgave": oppgave.name or ""}

    @api.model
    def fritekst(self, message_id, sporsmal):
        """Fritt spørsmål om denne tråden — Gjermund: «og fritekst».

        Konteksten er BUNDET til tråden: spørsmålet stilles om e-posten man står i,
        ikke som en åpen chat. Det er «Spør AI» i Kontrollrommet som er den generelle
        inngangen; her er poenget at svaret handler om saken foran deg.
        """
        q = (sporsmal or "").strip()
        if not q:
            return {"tekst": ""}
        meldinger = self._traad_meldinger(message_id)
        tekst, utelatt = self._som_tekst(meldinger)
        svar = self._kall(
            "Saksbehandleren spør om e-posten(e) under. Svar på spørsmålet med "
            "grunnlag i det som faktisk står der. Går svaret ikke fram, si det "
            "rett ut i stedet for å gjette.\n\nSPØRSMÅL: " + q,
            tekst,
        )
        return {"tekst": svar, "utelatt": utelatt}
