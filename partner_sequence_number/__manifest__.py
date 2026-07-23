# Copyright 2025 FIQ
# License HL3 or later (https://firstdonoharm.dev/build).

{
    "name": "Contact No.",
    "summary": "",
    "author": "FIQ",
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ir_sequence.xml",
        "views/res_partner_views.xml",
    ],
    "depends": [
        "base_display_name",
        "base_mixin_sequence_number",
        "res_company_code",
    ],
    "license": "AGPL-3",
    "version": "19.0.5.0.5",
    "website": "https://www.fiq.no",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
}
