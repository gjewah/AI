# -*- coding: utf-8 -*-
{
    "name": "FIQ AI (Claude connector)",
    "version": "19.0.1.0.0",
    "summary": "Claude (Anthropic API) connector for FIQ Odoo — chat, meeting summaries, AI search. "
               "Server-side; API key read from env var or system parameter, never stored in code.",
    "description": """
FIQ AI — Claude connector
=========================
A thin, reusable server-side connector that lets any FIQ module call Claude via the
Anthropic Messages API. Runs as the current user; the API key is read from the
ANTHROPIC_API_KEY environment variable, or the system parameter
``fiq_ai.anthropic_api_key`` as fallback. No key is ever kept in the source.

Entry points (call via env['fiq.ai']):
 * chat(prompt, system=None, model=None, max_tokens=1024) -> str
 * ping() -> str   (connection/key self-test)
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    "depends": ["base"],
    "data": [
        "security/ir.model.access.csv",
    ],
    "installable": True,
    "application": False,
}
