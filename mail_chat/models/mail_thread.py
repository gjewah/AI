from odoo import _, fields, models
from odoo.exceptions import UserError


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    default_chat_id = fields.Many2one(
        "mail.chat",
        string="Default Chat",
        index=True,
        copy=False,
        ondelete="set null",
    )

    def _mail_chat_get_or_create_default_chat(self):
        self.ensure_one()
        if self._name == "mail.chat":
            return self
        if not self.id:
            raise UserError(_("Please save the record before starting a chat conversation."))
        if not self.default_chat_id:
            chat = self.env["mail.chat"].sudo().create(
                {
                    "name": "Default",
                    "res_model": self._name,
                    "res_id": self.id,
                }
            )
            self.with_context(mail_chat_skip_follower_sync=True).sudo().write(
                {"default_chat_id": chat.id}
            )
            partner_ids = self.message_partner_ids.ids
            if partner_ids:
                chat.with_context(mail_chat_skip_follower_sync=True).message_subscribe(
                    partner_ids=partner_ids
                )
        return self.default_chat_id

    def action_create_chat(self, name, partner_ids=None):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the record before creating a chat."))
        chat = self.env["mail.chat"].create(
            {
                "name": name,
                "res_model": self._name,
                "res_id": self.id,
            }
        )
        if partner_ids:
            chat.message_subscribe(partner_ids=partner_ids)
        return chat.id

    def mail_chat_get_chats(self):
        self.ensure_one()
        if not self.id:
            return []
        self._mail_chat_get_or_create_default_chat()
        chats = self.env["mail.chat"].search(
            [("res_model", "=", self._name), ("res_id", "=", self.id)],
        )

        follower_data = self.env["mail.followers"].read_group(
            [("res_model", "=", "mail.chat"), ("res_id", "in", chats.ids)],
            ["res_id"],
            ["res_id"],
            lazy=False,
        )
        def _group_res_id(group):
            value = group.get("res_id")
            if isinstance(value, (list, tuple)):
                return value[0]
            return value

        def _group_count(group):
            return group.get("res_id_count", group.get("__count", 0))

        follower_count_by_chat = {
            _group_res_id(group): _group_count(group)
            for group in follower_data
            if _group_res_id(group)
        }

        attachment_data = self.env["ir.attachment"].read_group(
            [("res_model", "=", "mail.chat"), ("res_id", "in", chats.ids)],
            ["res_id"],
            ["res_id"],
            lazy=False,
        )
        attachment_count_by_chat = {
            _group_res_id(group): _group_count(group)
            for group in attachment_data
            if _group_res_id(group)
        }

        return [
            {
                "id": chat.id,
                "name": chat.name,
                "is_default": chat.id == self.default_chat_id.id,
                "sequence": chat.sequence,
                "followers_count": follower_count_by_chat.get(chat.id, 0),
                "attachments_count": attachment_count_by_chat.get(chat.id, 0),
            }
            for chat in chats
        ]

    def mail_chat_reorder(self, ordered_chat_ids):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the record before reordering chats."))

        ordered_chat_ids = [int(chat_id) for chat_id in (ordered_chat_ids or [])]
        if not ordered_chat_ids:
            return True

        chats = self.env["mail.chat"].search(
            [
                ("id", "in", ordered_chat_ids),
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
            ]
        )
        if len(chats) != len(set(ordered_chat_ids)):
            raise UserError(_("One or more chats are invalid for this record."))

        for index, chat_id in enumerate(ordered_chat_ids):
            self.env["mail.chat"].browse(chat_id).write({"sequence": (index + 1) * 10})
        return True

    def mail_chat_set_active(self, chat_id):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the record before setting an active chat."))
        chat = self.env["mail.chat"].browse(chat_id).exists()
        if not chat:
            raise UserError(_("Chat not found."))
        if chat.res_model != self._name or chat.res_id != self.id:
            raise UserError(_("The selected chat does not belong to this record."))
        return True

    def mail_chat_rename(self, chat_id, name):
        self.ensure_one()
        if not self.id:
            raise UserError(_("Please save the record before renaming a chat."))
        chat = self.env["mail.chat"].browse(chat_id).exists()
        if not chat:
            raise UserError(_("Chat not found."))
        if chat.res_model != self._name or chat.res_id != self.id:
            raise UserError(_("The selected chat does not belong to this record."))
        chat.write({"name": name})
        return True

    def message_subscribe(self, partner_ids=None, subtype_ids=None):
        result = super().message_subscribe(partner_ids=partner_ids, subtype_ids=subtype_ids)
        if self.env.context.get("mail_chat_skip_follower_sync") or self._name == "mail.chat":
            return result

        partner_ids = partner_ids or []
        if not partner_ids:
            return result

        for record in self:
            chat = record.default_chat_id
            if chat:
                chat.with_context(mail_chat_skip_follower_sync=True).message_subscribe(
                    partner_ids=partner_ids,
                    subtype_ids=subtype_ids,
                )
        return result

    def message_unsubscribe(self, partner_ids=None):
        result = super().message_unsubscribe(partner_ids=partner_ids)
        if self.env.context.get("mail_chat_skip_follower_sync") or self._name == "mail.chat":
            return result

        partner_ids = partner_ids or []
        if not partner_ids:
            return result

        for record in self:
            chat = record.default_chat_id
            if chat:
                chat.with_context(mail_chat_skip_follower_sync=True).message_unsubscribe(
                    partner_ids=partner_ids,
                )
        return result

    def message_post(self, **kwargs):
        if self.env.context.get("mail_chat_bypass_routing") or self._name == "mail.chat":
            return super().message_post(**kwargs)

        messages = self.env["mail.message"]
        for record in self:
            chat = record._mail_chat_get_or_create_default_chat()
            if not chat:
                raise UserError(_("Missing default chat for this record."))
            messages |= chat.with_context(mail_chat_bypass_routing=True).message_post(**kwargs)
        return messages
