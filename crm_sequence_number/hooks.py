def post_init_hook(env):
    Company = env["res.company"]
    lead_model = env["ir.model"].search([("model", "=", "crm.lead")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('sequence_number')} {r.name}"
    )
    lead_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )

def pre_uninstall_hook(env):
    lead_model = env["ir.model"].search([("model", "=", "crm.lead")])
    lead_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
