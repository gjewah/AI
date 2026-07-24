{
    "name": "Kommunikasjon",
    "version": "19.0.1.10.5",
    "summary": "FIQ Kommunikasjon – paraply-flaten for ALL kommunikasjon. "
    "E-post, WhatsApp, Teams og chat er KANALER inne i denne flaten.",
    "description": """
FIQ Kommunikasjon (paraply)
===========================
Gjermund-beslutning 17.07.2026: **flaten heter «Kommunikasjon» — ETT navn.**
«Meldingssenteret og Kommunikasjonssenteret — det er det samme.»

Denne modulen er PARAPLYEN:

* Eier kanal-filteret (Alle · E-post · WhatsApp · Teams · chat).
* Registrerer kanaler via et enkelt register, så nye kanaler kan komme til
  uten at paraplyen endres.
* Kanal-modulene selv (f.eks. ``fiq_gui_epost``) beholder sine tekniske navn
  og leverer INN hit. Ingen omdøping av installerte moduler
  («modul forsvinner mens installert»-fella).

Navnestandard: ``fiq_gui_<kode>`` (GUI-flate). ``fiq_ai_*`` er reservert
AI-MOTOREN (``fiq_ai_claude``) — ikke GUI-flater.

Kommunikasjon = paraply. E-post = ÉN kanal inne i den, vises ikke i hovedmenyen.
""",
    "author": "FIQ as",
    "website": "https://www.fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # `fiq_gui_shell` er nødvendig fordi comm.js registrerer seg i skallets
    # `fiq_gui_flates`-register. Uten avhengigheten er lasterekkefølgen tilfeldig, og
    # registreringen kan kjøre før registeret finnes — flaten blir da usynlig i
    # venstremenyen uten at noe feiler. Samme mønster som fiq_gui_rgs bruker.
    "depends": ["fiq_gui_control", "fiq_gui_shell", "web", "mail"],
    "data": [
        "security/fiq_gui_comm_groups.xml",
        "views/fiq_gui_comm_action.xml",
        "data/fiq_gui_comm_flate.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_comm/static/src/comm.scss",
            "fiq_gui_comm/static/src/comm.js",
            "fiq_gui_comm/static/src/comm.xml",
        ],
    },
    "application": True,
    "installable": True,
    "auto_install": False,
}
