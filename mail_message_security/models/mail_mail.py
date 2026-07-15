import logging
import traceback

from odoo import api, models
# from odoo.http import request
from odoo.tools.mail import email_split


_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    _inherit = "mail.mail"

    @api.model_create_multi
    def create(self, vals_list):
        """
        Do not notify recipients if the context indicates that the fetchmail cron is running.
        """
        if self.env.context.get("fetchmail_cron_running"):
            return self
        else:
            return super().create(vals_list)
