# -*- coding: utf-8 -*-
from . import models
from . import controllers


def _refresh_icon(env):
    import base64
    import os
    icon_path = os.path.join(os.path.dirname(__file__), 'static', 'description', 'icon.png')
    if os.path.exists(icon_path):
        with open(icon_path, 'rb') as f:
            icon_data = base64.b64encode(f.read())
        module = env['ir.module.module'].search([('name', '=', 'gdpr_platform')], limit=1)
        if module:
            module.write({'icon_image': icon_data})


def post_init_hook(env):
    _refresh_icon(env)


def uninstall_hook(env):
    pass
