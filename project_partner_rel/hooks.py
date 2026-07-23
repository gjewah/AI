from odoo import api, SUPERUSER_ID
from odoo.fields import Command

def post_init_hook(env):
    """
    Synchronize the partner_ids field with the partner_id field for existing projects.
    """
    # env = api.Environment(cr, SUPERUSER_ID, {})
    projects = env['project.project'].search([])
    for project in projects:
        if project.partner_id and not project.partner_ids:
            project.partner_ids = [Command.set([project.partner_id.id])]
