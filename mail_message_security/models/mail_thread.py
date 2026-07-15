import logging
import traceback

from odoo import models
# from odoo.http import request
from odoo.tools.mail import email_split


_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    def _notify_get_recipients(self, message, msg_vals, **kwargs):
        """
        Do not notify recipients if the context indicates that the fetchmail cron is running.
        """
        recipients_data = super()._notify_get_recipients(message, msg_vals, **kwargs)
        if self.env.context.get("fetchmail_cron_running"):
            Partner = self.env["res.partner"]
            email_to = email_split(msg_vals.get("email_to", ""))
            for recipient_data in recipients_data:
                if Partner.browse(recipient_data.get("id")).email not in email_to:
                    recipients_data.remove(recipient_data)
        return recipients_data
