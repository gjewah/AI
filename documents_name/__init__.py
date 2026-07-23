from . import models

def post_init_hook(env):
    env["documents.document"].search([])._set_name_or_name_translate()
