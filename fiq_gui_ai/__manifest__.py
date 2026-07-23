# -*- coding: utf-8 -*-
{
    "name": "FIQ AI co-worker",
    "version": "19.0.1.2.1",
    "summary": "FIQ AI co-worker: an 'Ask AI for help' chat (to Claude) plus Odoo "
               "presence – embeddable in the Control room and openable as its own flate.",
    "description": """
FIQ AI co-worker (fiq_gui_ai)
=============================
An 'Ask AI for help' chat field wired to Anthropic's Claude, plus a simple Odoo
presence panel (which internal users are online). Registered as an OWL client
action so it can be embedded in the Control room AND opened as a standalone flate.

Key features
 * "Ask AI for help" chat – input + send → answer list, in the same visual
   style as fiq_gui_control.
 * Backend model fiq.gui.ai.assistent with spor(): reads the Anthropic API key
   from ir.config_parameter (never hard-coded), calls the Messages API with
   `requests`, runs as the current user (record rules apply), and always returns
   a friendly Norwegian message instead of crashing if the key is missing or the
   call fails.
 * Presence – reads online status for internal users (res.users.im_status).
 * Access group "AI MGM" (AI Management) governs configuration; the chat is open
   to all internal users.
 * Fully translatable – English source, Norwegian (nb_NO) provided; follows the
   user's language.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "OPL-1",
    "depends": ["web", "mail"],
    "data": [
        "security/fiq_gui_ai_groups.xml",
        "security/ir.model.access.csv",
        "views/fiq_gui_ai_action.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Odoo 20-regel 30/31 (Gjermund 23.07): assets deklareres EKSPLISITT.
            # Wildcard skjuler lasterekkefolgen — og rekkefolgen mellom skall og flate
            # var nettopp det som felte grensesnittet 18.07. Stil, logikk, maler.
            "fiq_gui_ai/static/src/coworker.scss",
            "fiq_gui_ai/static/src/coworker.js",
            "fiq_gui_ai/static/src/coworker.xml",

        ],
    },
    "application": True,
    "installable": True,
}
