from . import models

def post_init_hook(env):
    for record in env["documents.tag"].search([]):
        record.tooltip_translate = record.tooltip
