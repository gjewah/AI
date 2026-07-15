def post_init_hook(env):
    Company = env["res.company"]
    project_model = env["ir.model"].search([("model", "=", "project.project")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('sequence_code')} {r.name}"
    )
    project_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )
    task_model = env["ir.model"].search([("model", "=", "project.task")])
    display_name_expression = (
        "{r.pick('company_code')} {r.pick('code')} {r.name}"
    )
    task_model.write(
        {
            "use_display_name_expression": True,
            "display_name_expression": display_name_expression,
        }
    )


def pre_uninstall_hook(env):
    project_model = env["ir.model"].search([("model", "=", "project.project")])
    project_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
    task_model = env["ir.model"].search([("model", "=", "project.task")])
    task_model.write(
        {
            "use_display_name_expression": False,
            "display_name_expression": "",
        }
    )
