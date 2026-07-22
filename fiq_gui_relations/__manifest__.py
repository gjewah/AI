# -*- coding: utf-8 -*-
{
    "name": "FIQ Relations",
    "version": "19.0.1.5.0",
    "summary": "Typed, directed relations between contacts, companies, properties and "
               "projects. One person, many affiliations - without duplicate contacts.",
    "description": """
FIQ Relations - one contact, many affiliations
===============================================
Odoo allows a contact only ONE parent (res.partner.parent_id, a many2one). A person who
works for several companies must therefore be entered several times, and the job title
lands on the *person* (res.partner.function) instead of on the *affiliation*.

Verified on the live base 2026-07-18: one human being existed as twelve contacts, three
of them carrying a different job title each because each pointed at a different parent.

This module adds a separate relation RECORD alongside parent_id, which is left untouched:

 * fiq.gui.relation       - one row = one relation: partner A -> type -> partner B,
                            with direction, validity period and company scope.
 * fiq.gui.relation.type  - configurable catalogue with a name in BOTH directions
                            ("is general manager of" / "has as general manager").

Why a record and not a Many2many: a plain many2many can only state THAT two records are
connected. It cannot carry the relation type, the direction, or the period - all three of
which the pairing engine needs to walk sender -> person -> affiliations -> related events.

Rights are deliberately NOT defined here. The module adds no res.groups of its own so it
can be attached to the platform-wide inherited-rights model (fiq_tilgang) without being
rewritten.
""",
    "author": "FIQ AS",
    "website": "https://fiq.no",
    "category": "Productivity/FIQ",
    "license": "LGPL-3",
    # fiq_gui_shell is NOT optional: the surface registers itself in the shell's
    # fiq_gui_flates registry, so it depends on the shell. Without the declaration the
    # load order is undefined - that was the root cause of the blank screen on 18.07
    # (registry collision, with a clean server log). Pattern copied from fiq_gui_rgs.
    "depends": ["base", "contacts", "fiq_gui_control", "fiq_gui_shell", "web"],
    "data": [
        "security/ir.model.access.csv",
        "data/fiq_gui_relation_type_data.xml",
        "views/fiq_gui_relation_views.xml",
        "views/res_partner_views.xml",
        "data/fiq_gui_relations_flate.xml",
        "data/fiq_gui_relation_cron.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "fiq_gui_relations/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
}
