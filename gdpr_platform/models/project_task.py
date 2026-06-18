# -*- coding: utf-8 -*-
# Copyright 2024 FIQ AS
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""project.task – GDPR block/unblock via mixin."""
from odoo import models


class ProjectTask(models.Model):
    """project.task inherits GdprPartnerMixin to expose block/unblock buttons."""

    _name = 'project.task'
    _inherit = ['project.task', 'gdpr.partner.mixin']
