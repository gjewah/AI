# -*- coding: utf-8 -*-
"""REGLENE — de elleve kontrollene, i klartekst.

Gjermund 23.07.2026, ordrett:
  «jeg vet ikke hva portene er»
  «sett opp disse reglene ... så jeg skjønner at det her er snakk om regler.
   dette er første gangen jeg ser disse»

🔴 DET ER SAKEN: øktene har brukt portnummer mot ham i to dager. Reglene ble laget
mellom AI-øktene og nådde aldri mennesket de skulle tjene. En regel han ikke kan
lese, er en regel som beskytter oss mot ham i stedet for å hjelpe ham.

═══ HVORDAN DE PRESENTERES ═══
  ❌ «PORT 7 — nettleser + bestilling»
  ✅ «Har et menneske åpnet flaten — og er det som ble bestilt?»  ·  07

Spørsmålet er overskriften. Nummeret er en liten merkelapp ved siden av, slik at
øktene fortsatt kan snakke sammen om «port 7» uten at Gjermund må lære tallene.

Kilde: `brain/00_FERDIG.md` (674 linjer). OVERSATT, ikke gjenfortalt — ingen
kommandolinjer, ingen sjargong. `psql`, `grep` og `ssh` hører i utvikler-
dokumentasjonen, ikke i flaten hans.
"""

from odoo import api, fields, models


class FiqAiRegel(models.AbstractModel):
    _name = "fiq.ai.regel"
    _description = "Reglene AI-øktene kvitterer mot — i klartekst"

    # Rekkefølgen er den samme som i kilden, fordi øktene kvitterer i rekkefølge.
    # `hvem`: "ai" = økta gjør det selv · "gjermund" = bare et menneske kan
    # Kun TO av elleve er hans. Det skal han se med én gang.
    REGLER = [
        {
            "nr": "00", "hvem": "ai",
            "sporsmaal": "Er modulen i det hele tatt installert?",
            "hvorfor": "En modul som ikke er installert kan ikke gjøre noe — uansett hvor "
                       "riktig koden er. Sjekkes FØRST, før noen leter etter andre årsaker.",
            "larte_vi": "En modul sto avinstallert i ti dager mens to økter bygde hver sin "
                        "forklaring på hvorfor den ikke virket. Svaret sto skrevet hele tiden.",
        },
        {
            "nr": "01", "hvem": "ai",
            "sporsmaal": "Snakker vi med en levende maskin?",
            "hvorfor": "DEV får nytt nummer hver gang den bygges på nytt. Den gamle maskinen "
                       "svarer fortsatt en stund — med full database.",
            "larte_vi": "En død maskin som svarer er verre enn en som ikke gjør det. Vi målte "
                        "på gårsdagens server og trodde alt sto bra til.",
        },
        {
            "nr": "02", "hvem": "ai",
            "sporsmaal": "Er koden i git, på serveren og i basen den SAMME?",
            "hvorfor": "Koden kan ligge tre steder i tre versjoner samtidig. Er de ulike, "
                       "måler vi noe annet enn det som kjører.",
            "larte_vi": "«Pushet til grenen» betyr ikke «ligger på serveren». Vi ba deg "
                        "oppgradere til en versjon som ikke fantes på maskinen.",
        },
        {
            "nr": "03", "hvem": "ai",
            "sporsmaal": "Har vi målt i det som kjører — eller bare lest i en fil?",
            "hvorfor": "At noe står skrevet i koden betyr ikke at Odoo har tatt det i bruk.",
            "larte_vi": "Et søk finner ordet, ikke funksjonen. Vi meldte fire ting som "
                        "«bygget» fordi navnet fantes i en kommentar.",
        },
        {
            "nr": "04", "hvem": "ai",
            "sporsmaal": "Virker det når det kjøres — ikke bare når det lastes?",
            "hvorfor": "At en side laster ned filene sine sier ingenting om at den virker.",
            "larte_vi": "En blank skjerm hadde tre ulike årsaker etter hverandre. Hver "
                        "«løsning» avdekket den neste.",
        },
        {
            "nr": "05", "hvem": "ai",
            "sporsmaal": "Virker det ved vanlig oppstart — uten spesialinnstillinger?",
            "hvorfor": "En rettelse som bare virker med egne flagg, er ikke en rettelse.",
            "larte_vi": "Vi meldte en feil som løst. Den kom tilbake ved neste ordinære "
                        "oppstart, fordi den bare virket med våre egne innstillinger.",
        },
        {
            "nr": "06", "hvem": "ai",
            "sporsmaal": "Er det testet med data som ligner virkeligheten?",
            "hvorfor": "En test som bruker pene tall vi har valgt selv, beviser lite.",
            "larte_vi": "42 grønne tester på tom base skjulte en feil som veltet hele flaten "
                        "med ekte data.",
        },
        {
            "nr": "07", "hvem": "gjermund",
            "sporsmaal": "Har et menneske åpnet flaten — og er det som ble bestilt?",
            "hvorfor": "Grønne tester beviser at koden gjør det den ble bedt om. De sier "
                       "ingenting om at flaten er brukbar, eller at vi bygde riktig ting.",
            "larte_vi": "Vi meldte «68 tester grønne, klar til bruk» om en flate som ikke "
                        "kunne rulles. Sant og villedende samtidig. Bare du kan lukke denne.",
        },
        {
            "nr": "08", "hvem": "ai",
            "sporsmaal": "Teller vi årsaker — eller bare linjer i en logg?",
            "hvorfor": "Én feil kan lage titalls loggmeldinger. Teller vi meldingene, ser det "
                       "ut som mange feil.",
            "larte_vi": "Vi meldte «125 advarsler» der det reelt var fire årsaker.",
        },
        {
            "nr": "09", "hvem": "ai",
            "sporsmaal": "Jobber noen andre i basen akkurat nå?",
            "hvorfor": "Flere økter deler samme database. Skriver to samtidig, kan begge feile "
                       "— eller verre: én overskriver den andre uten at noen ser det.",
            "larte_vi": "To installasjoner kolliderte i dag. Den ene meldte «0 tester, ingen "
                        "feil» — fordi ingenting i det hele tatt ble kjørt.",
        },
        {
            "nr": "10", "hvem": "gjermund",
            "sporsmaal": "Overlever endringen at miljøet bygges på nytt?",
            "hvorfor": "DEV bygges tom hver gang. Det som bare finnes der, forsvinner. Skal noe "
                       "bestå, må det til Staging og videre til Production.",
            "larte_vi": "Fire moduler falt ut da Staging ble hentet på nytt fra Production, "
                        "fordi de aldri var installert i Production.",
        },
    ]

    # Ord vi bruker mellom øktene, som Gjermund sa han ikke kjente.
    ORDLISTE = [
        ("DEV", "Testbenken. Bygges tom hver gang — data der forsvinner. "
                "Her prøver AI-en ut kode før den kommer videre."),
        ("Staging", "Kopi av Production å øve på. Data overlever her. "
                    "Det er hit du oppdaterer når noe er klart til å ses på."),
        ("Production", "Det ekte systemet, med ekte data. Ingenting skrives hit "
                       "uten at du har sagt ja først."),
        ("Pinne", "Et bokmerke som sier hvilken versjon av koden en server skal bruke. "
                  "Flyttes bokmerket ikke, henter serveren gammel kode."),
        ("Flate", "En skjerm i Kontrollrommet — Prosjekt, Finans, AI Kontrollrom."),
        ("Feilklasse", "En type feil som gjentar seg i ulik forkledning. Vi navngir dem "
                       "for å kjenne dem igjen raskere neste gang."),
        ("Kunstpause", "AI-en leverer én versjon og STOPPER — venter på din kommentar "
                       "før neste. Så du rekker å si fra før den bygger videre."),
    ]

    @api.model
    def get_regler(self):
        """Reglene slik flaten viser dem. Ingen kommandoer, ingen sjargong."""
        return {
            "regler": self.REGLER,
            "ordliste": [{"ord": o, "forklaring": f} for o, f in self.ORDLISTE],
            "krever_deg": len([r for r in self.REGLER if r["hvem"] == "gjermund"]),
            "totalt": len(self.REGLER),
        }
