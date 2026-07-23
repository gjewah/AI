from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MailChat(models.Model):
    _name = "mail.chat"
    _description = "Mail Chat"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"
    _mail_post_access = "read"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10, index=True)
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Integer(required=True, index=True)

    _sql_constraints = [
        (
            "mail_chat_unique_name_per_record",
            "unique(res_model, res_id, name)",
            "A chat with this name already exists for this record.",
        ),
    ]

    def init(self):
        self.env.cr.execute(
            """
            CREATE INDEX IF NOT EXISTS mail_chat_res_model_res_id_idx
            ON mail_chat (res_model, res_id)
            """
        )

    def _mail_chat_related_record(self):
        self.ensure_one()
        return self.env[self.res_model].browse(self.res_id).exists()

    @staticmethod
    def _normalize_chat_name(name):
        return (name or "").strip()

    @api.constrains("name", "res_model", "res_id")
    def _check_unique_name_case_insensitive(self):
        for chat in self:
            normalized_name = self._normalize_chat_name(chat.name)
            if not normalized_name or not chat.res_model or not chat.res_id:
                continue
            duplicate = self.search(
                [
                    ("id", "!=", chat.id),
                    ("res_model", "=", chat.res_model),
                    ("res_id", "=", chat.res_id),
                    ("name", "=ilike", normalized_name),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _("A chat with this name already exists for this record. Names are case-insensitive.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "name" in vals:
                vals["name"] = self._normalize_chat_name(vals["name"])
            if "sequence" in vals:
                continue
            res_model = vals.get("res_model")
            res_id = vals.get("res_id")
            if not (res_model and res_id):
                continue
            self.env.cr.execute(
                """
                SELECT COALESCE(MAX(sequence), 0)
                FROM mail_chat
                WHERE res_model = %s AND res_id = %s
                """,
                (res_model, res_id),
            )
            max_sequence = self.env.cr.fetchone()[0] or 0
            vals["sequence"] = max_sequence + 10
        return super().create(vals_list)

    def write(self, vals):
        if "name" in vals:
            vals["name"] = self._normalize_chat_name(vals["name"])
        return super().write(vals)

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        result = super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
        if self.env.context.get("mail_chat_skip_follower_sync"):
            return result
        partner_ids = partner_ids or []
        if not partner_ids:
            return result

        for chat in self:
            record = chat._mail_chat_related_record()
            if (
                record
                and "default_chat_id" in record._fields
                and record.default_chat_id.id == chat.id
            ):
                record.with_context(mail_chat_skip_follower_sync=True).message_subscribe(
                    partner_ids=partner_ids,
                    subtype_ids=subtype_ids,
                )
        return result

    def message_unsubscribe(self, partner_ids=None):
        result = super().message_unsubscribe(partner_ids=partner_ids)
        if self.env.context.get("mail_chat_skip_follower_sync"):
            return result
        partner_ids = partner_ids or []
        if not partner_ids:
            return result

        for chat in self:
            record = chat._mail_chat_related_record()
            if (
                record
                and "default_chat_id" in record._fields
                and record.default_chat_id.id == chat.id
            ):
                record.with_context(mail_chat_skip_follower_sync=True).message_unsubscribe(
                    partner_ids=partner_ids,
                )
        return result
