from odoo import api, SUPERUSER_ID

def migrate(cr, version):
    """
    Migrate existing parent_id/child_ids hierarchy to the new
    parent_ids/child_ids Many2many relation table.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1) Create the new M2M relation table if it doesn't exist
    cr.execute("""
        CREATE TABLE IF NOT EXISTS documents_tag_hierarchy_rel (
            parent_id INTEGER NOT NULL,
            child_id INTEGER NOT NULL,
            CONSTRAINT documents_tag_hierarchy_rel_pkey PRIMARY KEY (parent_id, child_id)
        )
    """)

    # 2) Fetch all tags with a parent using SQL
    cr.execute("""
        SELECT id, parent_id
        FROM documents_tag
        WHERE parent_id IS NOT NULL
    """)
    rows = cr.fetchall()

    for tag_id, parent_id in rows:
        # Insert into relation table if not already present
        cr.execute("""
            INSERT INTO documents_tag_hierarchy_rel (parent_id, child_id)
            SELECT %s, %s
            WHERE NOT EXISTS (
                SELECT 1 FROM documents_tag_hierarchy_rel
                WHERE parent_id = %s AND child_id = %s
            )
        """, (parent_id, tag_id, parent_id, tag_id))
