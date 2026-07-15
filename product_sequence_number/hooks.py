def post_init_hook(env):
    Company = env["res.company"]
    template_model = env["ir.model"].search([("model", "=", "product.template")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('sequence_number')} {r.name}"
    )
    template_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )
    variant_model = env["ir.model"].search([("model", "=", "product.product")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('sequence_number')} {r.name}"
    )
    variant_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )


def pre_uninstall_hook(env):
    template_model = env["ir.model"].search([("model", "=", "product.template")])
    template_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
    variant_model = env["ir.model"].search([("model", "=", "product.product")])
    variant_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
