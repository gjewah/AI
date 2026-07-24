# ruff: noqa: B018 — Odoos manifest ER en ordbok paa toppnivaa, ikke et uttrykk paa avveie
{
    "name": "FIQ AI KR – AI Kontrollrom",
    "version": "19.0.3.2.4",
    "summary": "FIQ AI Kontrollrom (AI KR) – operatør-cockpit: oversikt over alle AI-økter "
    "(Claude Code + Cowork), AI-organisasjonskart, redigerbare roller/skills, "
    "ressursbruk og ROI. Snippet-basert (firma → rolle → person).",
    "description": """19.0.3.2.4 - LINT REN: 13 funn rettet (AI PK maalte dem i gaten):
* 12 UP031 (%-formatering) + 1 E741 (variabelnavnet `l`). AI PK la modulen inn
  i apps-ai, kjorte port 1, og tok den UT igjen - den var ikke klar.
* 🔴 NULLPOLSTRINGEN BEVART, og BEVIST: %02d -> :02d. Uten den ville «01.03»
  blitt «1.3» og oektnavnet sluttet aa matche registeret. Lint ville vaert HELT
  STILLE. Kjort som sammenlikning for/etter paa ekte verdier:
      versjon:  '01.03' == '01.03'
      oektnavn: '0.00 8.50 AI KR (01.03)' == samme
      alder:    likt for 5/90/3000 minutter · bilde-url likt
* 🔑 TUPPEL-FELLA SJEKKET FOERST (AI PKs advarsel): alle 12 hoyresider er
  eksplisitte uttrykk, ingen funksjonskall som kan gi tuppel. Hadde en av dem
  vaert det, ville f-strengen gitt «(2026, 30)» i stedet for «2026-30».
* E741: BEGGE forekomstene paa linja byttet samtidig (`l` -> `rad`). Kommunikasjon
  byttet loekkevariabelen og lot `l.name` staa - NameError ved kjoering, ruff stille.
* Rekkefolgen AI PK krevde: format -> check EEN GANG TIL (UP031-kjeden gir UP032).
  Resultat: All checks passed · 18 files already formatted.


FIQ AI KR – AI Kontrollrom
==========================
Operatør-cockpit for FIQ AI-plattformen. Bygger VIDERE på eksisterende grunnlag
(get_cockpit i fiq_gui_control + fiq_ai/fiq_ai_claude) – aldri fra scratch.

Increment 2.01 (denne versjonen): data-lag for OPPGAVE-OVERSIKT – samler alle
AI-økter/oppgaver (Claude Code + Cowork) som er logget i Odoo, med 👤/🤖-merke,
status og «krever handling». Config-drevet rot-prosjekt (systemparameter
fiq_gui_ai_kr.okter_project_id), firma-scoping klar for firma-snippet.

19.0.2.1.0 — NATIVE VIEWS for øktregisteret (KANON «Odoo-native først», Gjermund 16.07.2026):
`fiq.ai.okt` fantes som modell + registrer_okt(), men UTEN egne views — øktregisteret var
usynlig i Odoo uten KR-flaten. Testen «Virker dette i native Odoo uten KR?» besto ikke.
Nå: liste (farget på status) · skjema · søk m/ filtre (aktive/pause/feilet/**stille >1 døgn**)
+ gruppering (status/kilde/firma/dag) · menypunkt «AI-økter» under AI Kontrollrom-roten.
TVILLING-PRINSIPPET: dette er `brain/okt_register.md` som LEVENDE Odoo-tabell. Claude fører
den selv — Gjermund rører den aldri. Løser den dokumenterte floka med utdaterte økt-id-er
i md-registeret (AI PK-raden pekte 16.07.2026 på en id som ikke finnes).

Kommer i senere increments:
 * AI-organisasjonskart (roller/skills som AI-ansatte per firma)
 * Redigerbare stillingsbetegnelser på roller + skills (rådgivere) – CRUD uten kode
 * Ressursbruk (tokens/USD) + ROI – via Anthropic Admin API (menneske-gate: Admin-nøkkel)
 * Snippet-rammeverk – sett sammen delene selv, per firma / rolle / person

Add-only: rører IKKE den frosne KR-kjernen (fiq_gui_control 6.7xx). Plugges inn
som flate i det delte skallet (Vei C).
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # 🛑 `fiq_gui_shell` er IKKE valgfri: skall-registreringen i ai_kr.js kjører mot
    # registryet skallet eier. Uten avhengigheten er lasterekkefølgen udefinert — det
    # var rotårsaken til blank skjerm 18.07.2026 (meldt av fiq_gui_control 22.07).
    "depends": [
        "fiq_gui_control",
        "fiq_gui_shell",
        "fiq_gui_comm",
        "web",
        "project",
        "mail",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/ai_kr_action.xml",
        "views/fiq_ai_okt_views.xml",
        "views/fiq_ai_spor_views.xml",
        "views/fiq_ai_melding_views.xml",
        "views/styring_action.xml",
        "data/fiq_ai_spor_data.xml",
        "data/fiq_gui_ai_kr_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_ai_kr/static/src/ai_kr.scss",
            "fiq_gui_ai_kr/static/src/styring/styring.scss",
            "fiq_gui_ai_kr/static/src/ai_kr.js",
            "fiq_gui_ai_kr/static/src/styring/styring.js",
            "fiq_gui_ai_kr/static/src/ai_kr.xml",
            "fiq_gui_ai_kr/static/src/styring/styring.xml",
        ],
    },
    "application": False,
    "installable": True,
}
