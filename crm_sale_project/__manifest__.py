# Copyright 2025 Loym
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

{
    "name": "CRM: Create sale order and project",
    "summary": "",
    "author": "FIQ, Loym",
    "data": [
        "views/crm_lead_views.xml",
        "views/project_project_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "depends": [
        # "base_mixin_sequence_number", # "base_mixin_expression_value",
        # "crm_security_group",
        "crm_name",
        "crm_timesheet", # lead.project_id
        "partner_short_name",
        "portal_user", # dummy placeholders
        "sale_crm",
        "sale_project",
        "sale_timesheet", # to avoid: Invalid field 'billing_type' on model 'project.project'
    ],
    "license": "AGPL-3",
    "version": "19.0.5.0.13",
    "website": "https://www.loym.com",
}
