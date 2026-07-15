def post_init_hook(env):
    Company = env["res.company"]
    documents_model = env["ir.model"].search([("model", "=", "documents.document")])
    display_name_expression = (
        ("{r.pick('company_id.code')} " if Company._fields.get("code") else "")
        +
        "{r.pick('code')} {r.name}"
    )
    documents_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )


def pre_uninstall_hook(env):
    documents_model = env["ir.model"].search([("model", "=", "documents.document")])
    documents_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
