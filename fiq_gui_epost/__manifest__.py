# -*- coding: utf-8 -*-
{
    "name": "Meldingssenter",
    "version": "19.0.4.2.0",
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
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["fiq_gui_control", "web", "mail"],
    "data": [
        "security/fiq_gui_epost_groups.xml",
        "views/fiq_gui_epost_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # NB: kun static/src bundles. V00.04-flaten bor i static/v0104/ og serveres
            # av controlleren – den skal IKKE inn i asset-bunten.
            "fiq_gui_epost/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
