# Copyright 2025 Loym AS
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class Base(models.AbstractModel):
    _inherit = "base"

    def _notify_get_reply_to(self, default=None, author_id=False):
        """
        Always reply to the default email address if provided,
        in addition to the existing reply_to logic.
        """
        reply_to = super()._notify_get_reply_to(default=default, author_id=author_id)
        if default and isinstance(reply_to, dict):
            for k, v in reply_to.items():
                reply_to[k] = ", ".join([v, default])
        return reply_to
