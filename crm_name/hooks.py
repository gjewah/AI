def post_init_hook(env):
    param_key = "crm_name.crm_lead_name_expression"
    default_value = "{r.partner_id.short_name if r.partner_id.short_name else r.partner_id.name}"

    env['ir.config_parameter'].sudo().set_param(param_key, default_value)
