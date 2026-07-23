# Copyright 2026 FIQ
# License HL3 or later (https://firstdonoharm.dev/build).
{
    "name": "Product No.",
    "summary": "Product sequence number management",
    "version": "19.0.5.0.5",
    "author": "FIQ",
    "website": "https://www.fiq.no",
    "license": "AGPL-3",
    "category": "Product",
    "depends": [
        "base_display_name",
        "base_mixin_sequence_number",
        "product",
        "res_company_code",
    ],
    "data": [
        "data/ir_actions_server_data.xml",
        "data/ir_sequence.xml",
        "views/product_product_views.xml",
        "views/product_template_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "pre_uninstall_hook",
}
