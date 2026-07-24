{
    "name": "FIQ GUI Skall (V00.04 delt skall)",
    "version": "19.0.1.7.2",
    "summary": "Vei C: delt V00.04-skall — fast presence-linje + firma-band + sidemeny + innmat-slot. "
    "Flatene registrerer innmaten sin i registry-kategorien 'fiq_gui_flates'; klikk i "
    "sidemenyen bytter INNMAT, ikke hele siden. PULS-KR blir én flate til slutt (med S07).",
    "description": """
FIQ GUI Skall — det delte V00.04-skallet (Vei C)
==================================================
Det YTRE skallet alle KR-flatene plugges inn i. Skallet eier den faste chromen
(«TIL STEDE NÅ»-linje · firma-band · venstre sidemeny · låst tema) og en slot i midten.
Hver flate (Meldingssenter, Prosjekt, Salg …) registrerer sin innmat-komponent i
registry-kategorien «fiq_gui_flates» — skallet bygger sidemenyen fra registret og
rendrer valgt flate i sloten UTEN full page-swap.

Data: skallet finner ikke opp sin egen sikkerhet. Firmavelger, branding (logo/aksent) og
«TIL STEDE NÅ» leses fra fiq_gui_control (get_my_config / get_presence), som avgrenser
server-side via tillatte_firmaer() — fail-closed. Firmabytte går gjennom Odoos EGEN
user.activateCompanies, slik at resten av Odoo ser samme aktive firma som skallet viser.

Endrer IKKE fiq_gui_control sin kode (PULS-KR) — det LESER den. PULS blir en registrert
flate SIST.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    # fiq_gui_control eier fiq.gui.control.config — skallet henter firmaer (tillatte_firmaer,
    # fail-closed), branding og «til stede nå» DERFRA i stedet for å duplisere sikkerhets-
    # og scope-logikk. Ekte avhengighet: uten KR finnes ikke modellen skallet kaller.
    "depends": ["web", "fiq_gui_control"],
    "data": [
        "security/fiq_gui_shell_groups.xml",
        "views/fiq_gui_shell_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_shell/static/src/shell.scss",
            "fiq_gui_shell/static/src/demo_flates.js",
            "fiq_gui_shell/static/src/shell.js",
            "fiq_gui_shell/static/src/shell.xml",
        ],
    },
    "application": True,
    "installable": True,
}
