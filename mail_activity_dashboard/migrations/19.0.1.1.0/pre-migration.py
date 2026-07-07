# FIQ fiqas 18->19: opprydding av to etternoelere uten 19-kode.
# Ligger i mail_activity_dashboard (vert-modul) fordi base/upgrades aldri
# kjoerer i Odoo.sh-staging-flyten (base er allerede 19 naar vaar kode er
# til stede). Idempotent — trygg aa kjoere flere ganger; gjenbrukes ved
# Production-cutover. Merker: grep "FIQ 18->19" i loggen.
import logging

_logger = logging.getLogger("fiq.upgrade")

LEFTOVERS = ["mail_quoted_reply", "project_timesheet_time_control"]


def migrate(cr, version):
    _logger.warning("FIQ 18->19 leftover-opprydding STARTET (version=%s)", version)
    for module in LEFTOVERS:
        cr.execute("SELECT state FROM ir_module_module WHERE name=%s", (module,))
        row = cr.fetchone()
        if not row:
            _logger.warning("FIQ 18->19 %s finnes ikke - hopper over", module)
            continue
        # 1) Deaktiver visninger/menyer modulen eier (18-arkitektur; 19-utgaven
        #    eies av etterfoelgeren hr_timesheet_time_control / native mail)
        cr.execute(
            """UPDATE ir_ui_view SET active = false
                WHERE id IN (SELECT res_id FROM ir_model_data
                              WHERE module=%s AND model='ir.ui.view')""",
            (module,),
        )
        views = cr.rowcount
        cr.execute(
            """UPDATE ir_ui_menu SET active = false
                WHERE id IN (SELECT res_id FROM ir_model_data
                              WHERE module=%s AND model='ir.ui.menu')""",
            (module,),
        )
        menus = cr.rowcount
        # 2) Fjern kun metadata-pekerne; selve felt-/modell-postene deles med
        #    etterfoelger og standard og skal IKKE slettes
        cr.execute("DELETE FROM ir_model_data WHERE module=%s", (module,))
        imd = cr.rowcount
        # 3) Merk modulen som avinstallert
        cr.execute(
            """UPDATE ir_module_module
                  SET state='uninstalled', latest_version=NULL
                WHERE name=%s AND state NOT IN ('uninstalled','uninstallable')""",
            (module,),
        )
        _logger.warning(
            "FIQ 18->19 %s ryddet: %s visninger + %s menyer deaktivert, "
            "%s metadata-pekere fjernet, state var %s",
            module, views, menus, imd, row[0],
        )
    _logger.warning("FIQ 18->19 leftover-opprydding FERDIG")
