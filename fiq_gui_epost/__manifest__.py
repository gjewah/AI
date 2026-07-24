{
    # Paraplyen (fiq_gui_comm) eier navnet «Kommunikasjon» utad. Denne modulen er
    # E-POST-KANALEN under den → egen etikett, ellers to like app-fliser i Apper.
    # Teknisk modulnavn (fiq_gui_epost) er URØRT — modulen er live på Staging + Production.
    "name": "Kommunikasjon — E-post",
    "version": "19.0.7.1.0",
    "summary": "FIQ Meldingssenter – kommunikasjonsflaten i Kontrollrommet. "
    "V00.04-designet (godkjent) som levende flate: tilstede-topplinje, firmavelger "
    "m/ logo, taksonomi 0–8, kompakte meldingsrader, lesepanel, paring/tildeling og AI-flate.",
    "description": """
FIQ Meldingssenter (V00.04)
===========================
Kommunikasjonsflaten i FIQ AI Kontrollrommet.

Denne versjonen (v1) leverer den GODKJENTE V00.04-flaten som en levende flate i Odoo:
 * OWL klient-handling «Meldingssenter» (samme handling-tag som før → KR-sidemenyen fungerer).
 * Egen rute som serverer V00.04-flaten isolert, med avgrenset CSP (inline stil/skript + data:-logoer).
 * Ingen endring i KR-kjernen (fiq_gui_control / 6.7xx) – flaten står på egne ben.

Bakgrunn: beslutnings-notatet «Skal V00.04 bli KR-master?» (Alt C – gradvis).
V00.04 bygges først som levende referanse; native OWL-port mot ekte Odoo-data
(mail_fiq + paringshjerne fiq_komm_match) kommer i neste versjon etter master-beslutningen.
""",
    "author": "FIQ as",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # fiq_gui_comm = Kommunikasjon-paraplyen. E-post er en KANAL under den og melder
    # seg inn i kanal-registeret (models/fiq_gui_epost_kanal.py) → paraplyen må lastes
    # først. Enveis: comm avhenger ALDRI av epost (ingen sirkulær avhengighet).
    # fiq_ai = ÉN AI-vei (shim mot Odoo 19 native `ai` → Anthropic via fiq_ai_claude).
    # Verifisert installert i Production 24.07: fiq_ai 19.0.1.2.0 · ai 19.0.1.0.
    # project = sjekkliste legges som deloppgaver på project.task (Odoo 19s egen
    # mekanikk) — vi lager ikke en konkurrerende sjekkliste-modell ved siden av.
    # crm = «opprett salgsmulighet» fra en e-post (Gjermund 24.07). Verifisert
    # installert i Production 24.07 (crm 19.0.1.9). Koden sjekker likevel
    # «crm.lead in env» før bruk — en avhengighet i manifestet er ikke det samme
    # som en garanti på hver base.
    "depends": [
        "fiq_gui_comm",
        "fiq_gui_control",
        "fiq_ai",
        "project",
        "crm",
        "web",
        "mail",
    ],
    "data": [
        "security/fiq_gui_epost_groups.xml",
        "security/ir.model.access.csv",
        "security/fiq_gui_epost_rules.xml",
        "views/fiq_gui_epost_action.xml",
        "views/fiq_gui_epost_regel_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # NB: kun static/src bundles. V00.04-flaten bor i static/v0104/ og serveres
            # av controlleren – den skal IKKE inn i asset-bunten.
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_epost/static/src/epost.scss",
            "fiq_gui_epost/static/src/epost.js",
            "fiq_gui_epost/static/src/epost.xml",
        ],
    },
    # IKKE lenger egen app-flis: E-post er en KANAL inne i Kommunikasjon-paraplyen,
    # ikke en selvstendig app (Gjermund 17.07.2026: «e-post skal ikke vises før vi er
    # inne i kommunikasjonssenteret»). Paraplyen fiq_gui_comm er application=True.
    "application": False,
    "installable": True,
}
