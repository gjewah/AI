def migrate(cr, version):
    def has_col(table, col):
        cr.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name=%s AND column_name=%s", (table, col))
        return bool(cr.fetchone())

    # Migrer KUN der legacy-kolonnen unique_code finnes (eldre loym-skjema).
    # DB-er uten unique_code (f.eks. fiqas) har numrene i sequence_code allerede -> trygt no-op.
    if has_col("project_project", "unique_code"):
        cr.execute("""
            ALTER TABLE project_project
                ADD COLUMN IF NOT EXISTS sequence_sequence varchar,
                ADD COLUMN IF NOT EXISTS sequence_code varchar;
            UPDATE project_project
               SET sequence_sequence = sequence_code,
                   sequence_code = unique_code
             WHERE unique_code IS NOT NULL;
        """)
    if has_col("project_task", "unique_code"):
        cr.execute("""
            ALTER TABLE project_task ADD COLUMN IF NOT EXISTS code varchar;
            UPDATE project_task SET code = unique_code WHERE unique_code IS NOT NULL;
        """)
    if has_col("res_partner", "unique_code"):
        cr.execute("""
            ALTER TABLE res_partner ADD COLUMN IF NOT EXISTS sequence_number varchar;
            UPDATE res_partner SET sequence_number = unique_code WHERE unique_code IS NOT NULL;
        """)
    if has_col("crm_lead", "unique_code"):
        cr.execute("""
            ALTER TABLE crm_lead ADD COLUMN IF NOT EXISTS sequence_number varchar;
            UPDATE crm_lead SET sequence_number = unique_code WHERE unique_code IS NOT NULL;
        """)
    if has_col("product_template", "unique_code"):
        cr.execute("""
            ALTER TABLE product_template ADD COLUMN IF NOT EXISTS sequence_number varchar;
            UPDATE product_template SET sequence_number = unique_code WHERE unique_code IS NOT NULL;
        """)
    if has_col("product_product", "unique_code"):
        cr.execute("""
            ALTER TABLE product_product ADD COLUMN IF NOT EXISTS sequence_number varchar;
            UPDATE product_product SET sequence_number = unique_code WHERE unique_code IS NOT NULL;
        """)
