def post_init_hook(env):
    Company = env["res.company"]
    project_model = env["ir.model"].search([("model", "=", "project.project")])
    if project_model._fields.get("display_name_expression"):
        display_name_expression = (
            ("{r.pick('company_id.code')} " if Company._fields.get("code") else "")
            +
            "P{r.pick('internal_external')}{r.pick('sequence_code')} {r.name}"
        )
        project_model.write(
            {
                "use_display_name_expression": True,
                "display_name_expression": display_name_expression,
            }
        )


def pre_uninstall_hook(env):
    Company = env["res.company"]
    project_model = env["ir.model"].search([("model", "=", "project.project")])
    if project_model._fields.get("display_name_expression"):
        display_name_expression = (
            ("{r.pick('company_id.code')} " if Company._fields.get("code") else "")
            +
            "{r.pick('sequence_code')} {r.name}"
        )
        project_model.write(
            {
                "use_display_name_expression": True,
                "display_name_expression": display_name_expression,
            }
        )
