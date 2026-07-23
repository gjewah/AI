# Copyright 2025 Loym AS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    # @api.returns('mail.message', lambda value: value.id)
    # def message_post(self, **kwargs):
    #     self = self.with_context(
    #         force_notification_by_email=True # FIXME: Get the value from somewhere
    #     )
    #     return super().message_post(**kwargs)
