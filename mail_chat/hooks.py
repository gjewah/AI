from odoo import SUPERUSER_ID, api


def _iter_records_with_messages(env):
    env.cr.execute(
        """
        SELECT DISTINCT model, res_id
        FROM mail_message
        WHERE model IS NOT NULL
          AND res_id IS NOT NULL
          AND model != 'mail.chat'
        """
    )
    for model, res_id in env.cr.fetchall():
        if model not in env:
            continue
        record = env[model].browse(res_id).exists()
        if not record:
            continue
        if "default_chat_id" not in record._fields:
            continue
        yield record


def _as_env(arg, registry=None):
    if hasattr(arg, "cr") and hasattr(arg, "uid"):
        return arg
    return api.Environment(arg, SUPERUSER_ID, {})


def post_init_hook(env_or_cr, registry=None):
    env = _as_env(env_or_cr, registry=registry)

    for record in _iter_records_with_messages(env):
        chat = record.default_chat_id
        if not chat:
            chat = env["mail.chat"].create(
                {
                    "name": "Default",
                    "res_model": record._name,
                    "res_id": record.id,
                }
            )
            record.with_context(mail_chat_skip_follower_sync=True).write(
                {"default_chat_id": chat.id}
            )
            partner_ids = record.message_partner_ids.ids
            if partner_ids:
                chat.with_context(mail_chat_skip_follower_sync=True).message_subscribe(
                    partner_ids=partner_ids
                )

        env["mail.message"].search(
            [
                ("model", "=", record._name),
                ("res_id", "=", record.id),
            ]
        ).write(
            {
                "model": "mail.chat",
                "res_id": chat.id,
            }
        )


def uninstall_hook(env_or_cr, registry=None):
    env = _as_env(env_or_cr, registry=registry)
    messages = env["mail.message"].search([("model", "=", "mail.chat")])

    for message in messages:
        chat = env["mail.chat"].browse(message.res_id).exists()
        if not chat:
            continue

        values = {
            "model": chat.res_model,
            "res_id": chat.res_id,
        }
        if chat.name != "Default":
            body = message.body or ""
            values["body"] = f"[{chat.name}]\\n{body}"

        message.write(values)
