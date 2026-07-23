def post_init_hook(env):
    Company = env["res.company"]
    partner_model = env["ir.model"].search([("model", "=", "res.partner")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('sequence_number')} {r.name}"
    )
    partner_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )

def pre_uninstall_hook(env):
    partner_model = env["ir.model"].search([("model", "=", "res.partner")])
    partner_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
