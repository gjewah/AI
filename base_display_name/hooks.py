def pre_init_hook(env):
    env.cr.execute("""
        ALTER TABLE ir_model
        ADD COLUMN IF NOT EXISTS display_name_expression VARCHAR DEFAULT '';
    """)
