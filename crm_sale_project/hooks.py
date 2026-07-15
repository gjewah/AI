def post_init_hook(env):
    param_key = "crm_name.crm_lead_name_expression"
    default_value = "{r.get_partner_name_and_project_address(' - ')}"

    env['ir.config_parameter'].sudo().set_param(param_key, default_value)
