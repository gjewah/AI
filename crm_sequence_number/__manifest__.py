# Copyright (C) 2025 FIQ
# License HL3 or later (https://firstdonoharm.dev/build).


{
    "name": "Lead/Opportunity No.",
    "version": "19.0.5.0.3",
    "author": "FIQ",
    "website": "https://www.fiq.no",
    "license": "LGPL-3",
    "category": "",
    "depends": [
        "base_display_name",
        "base_mixin_sequence_number",
        "crm",
        "res_company_code",
    ],
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ir_sequence.xml",
        "views/crm_lead_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
}
