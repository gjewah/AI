# Copyright 2025 FIQ
# License HL3 or later (https://firstdonoharm.dev/build).

{
    "name": "Project/Task No.",
    "summary": "Project and task sequence number management",
    "author": "FIQ",
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ir_sequence.xml",
        "views/project_project_views.xml",
        "views/project_task_views.xml",
    ],
    "depends": [
        "base_display_name",
        "base_mixin_sequence_number",
        "project",
        "res_company_code",
    ],
    "excludes": [""],
    "license": "AGPL-3",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
    "version": "19.0.5.0.8",
    "website": "https://www.fiq.no",
}
