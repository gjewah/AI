from odoo import api, SUPERUSER_ID

def migrate(cr, version):

    cr.execute("""
        ALTER TABLE documents_document
        ADD COLUMN documents_tag_id integer;

        UPDATE documents_document
        SET documents_tag_id = tag_id
        WHERE tag_id IS NOT NULL;
    """)
