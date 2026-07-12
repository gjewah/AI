# -*- coding: utf-8 -*-
{
    "name": "FIQ GUI Skall (V00.04 delt skall)",
    "version": "19.0.1.0.0",
    "summary": "Vei C: delt V00.04-skall — fast presence-linje + firma-band + sidemeny + innmat-slot. "
               "Flatene registrerer innmaten sin i registry-kategorien 'fiq_gui_flates'; klikk i "
               "sidemenyen bytter INNMAT, ikke hele siden. PULS-KR blir én flate til slutt (med S07).",
    "description": """
FIQ GUI Skall — det delte V00.04-skallet (Vei C)
================================================
Det YTRE skallet alle KR-flatene plugges inn i. Skallet eier den faste chromen
(«TIL STEDE NÅ»-linje · firma-band · venstre sidemeny · låst tema) og en slot i midten.
Hver flate (Meldingssenter, Prosjekt, Salg …) registrerer sin innmat-komponent i
registry-kategorien «fiq_gui_flates» — skallet bygger sidemenyen fra registret og
rendrer valgt flate i sloten UTEN full page-swap.

Rører IKKE fiq_gui_control (PULS-KR, 6.7xx frosset) — PULS blir en registrert flate SIST, med S07.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["web"],
    "data": [
        "security/fiq_gui_shell_groups.xml",
        "views/fiq_gui_shell_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_shell/static/src/**/*",
        ],
    },
    "application": True,
    "installable": True,
}
