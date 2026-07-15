# Copyright 2025 FIQ
# License HL3 or later (https://firstdonoharm.dev/build).

{
    "name": "Internal/External Projects",
    "summary": "Manage internal and external projects",
    "author": "FIQ",
    "data": [
        "views/project_project_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "depends": [
        "project",
    ],
    "excludes": [""],
    "license": "LGPL-3",
    "version": "19.0.5.0.6",
    "website": "https://www.fiq.no",
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
}
