# FIQ fiqas 18->19 runde 2: documents_name er overfloedig i 19 (native name er
# flerspraaklig). FOER modulen pensjoneres: flett oversettelser fra
# name_translate inn i native name (kun noekler som mangler — ingenting
# overskrives, kolonnen name_translate blir staaende som sikkerhet).
# Idempotent; gjenbrukes ved Production-cutover. Merker: "FIQ 18->19".
import logging

_logger = logging.getLogger("fiq.upgrade")

MODULE = "documents_name"


def migrate(cr, version):
    _logger.warning("FIQ 18->19 documents_name-runde STARTET (version=%s)", version)
    # 0) Kjoer kun hvis kolonnen finnes (18-arv)
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name='documents_document' AND column_name='name_translate'"
    )
    if not cr.fetchone():
        _logger.warning("FIQ 18->19 name_translate finnes ikke - hopper over")
        return
    # 1) Flett: behold native name-verdier, legg til spraaknoekler som bare
    #    finnes i name_translate (jsonb || : hoeyre side vinner ved konflikt)
    cr.execute(
        """UPDATE documents_document
              SET name = COALESCE(name_translate, '{}'::jsonb) || COALESCE(name, '{}'::jsonb)
            WHERE name_translate IS NOT NULL
              AND EXISTS (
                    SELECT 1 FROM jsonb_object_keys(name_translate) k
                     WHERE NOT (name ? k))"""
    )
    _logger.warning("FIQ 18->19 flettet oversettelser inn i name: %s dokumenter", cr.rowcount)
    # 2) Pensjoner modulen (samme trygge moenster som leftover-oppryddingen)
    cr.execute(
        """UPDATE ir_ui_view SET active = false
            WHERE id IN (SELECT res_id FROM ir_model_data
                          WHERE module=%s AND model='ir.ui.view')""",
        (MODULE,),
    )
    views = cr.rowcount
    cr.execute("DELETE FROM ir_model_data WHERE module=%s", (MODULE,))
    imd = cr.rowcount
    cr.execute(
        """UPDATE ir_module_module
              SET state='uninstalled', latest_version=NULL
            WHERE name=%s AND state NOT IN ('uninstalled','uninstallable')""",
        (MODULE,),
    )
    _logger.warning(
        "FIQ 18->19 documents_name pensjonert: %s visninger deaktivert, %s pekere fjernet",
        views, imd,
    )
    _logger.warning("FIQ 18->19 documents_name-runde FERDIG")
