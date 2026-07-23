# Copyright 2025 Loym
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "Assign Partner Location",
    "summary": "",
    "author": "FIQ, Loym",
    "data": [
        "security/ir.model.access.csv",
        "views/res_city_zip_views.xml",
        "views/res_city_views.xml",
        "views/res_country_state_views.xml",
        "views/res_country_views.xml",
        "views/res_partner_assign_location_views.xml",
        "views/res_partner_views.xml",
    ],
    "depends": [
        "base_address_extended",
        "base_location",
        "contacts",
    ],
    "license": "AGPL-3",
    "version": "19.0.5.0.2",
    # "website": "https://www.loym.com",
}
