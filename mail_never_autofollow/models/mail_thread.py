# Copyright 2025 Loym AS
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model_create_multi
    def create(self, vals_list):
        self = self.with_context(
            mail_create_nosubscribe=True,
        )
        return super().create(vals_list)


    def message_post(self, **kwargs):
        self = self.with_context(
            mail_create_nosubscribe=True,
            mail_post_autofollow=False,
        )
        return super().message_post(**kwargs)

"""
    MailThread features can be somewhat controlled through context keys :

     - ``mail_create_nosubscribe``: at create or message_post, do not subscribe
       uid to the record thread
     - ``mail_create_nolog``: at create, do not log the automatic '<Document>
       created' message
     - ``mail_notrack``: at create and write, do not perform the value tracking
       creating messages
     - ``tracking_disable``: at create and write, perform no MailThread features
       (auto subscription, tracking, post, ...)
     - ``mail_notify_force_send``: if less than 50 email notifications to send,
       send them directly instead of using the queue; True by default
"""
