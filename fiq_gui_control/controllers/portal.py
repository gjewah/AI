# -*- coding: utf-8 -*-
"""
Portal reuse (sketch).

The Control room is built generically so that the CORE (the KPI/widget model + data
sources) can be reused in a portal solution for external users (free portal users, cf.
the FIQ customer portal pattern). The backend version (OWL client action) is primary
here; the portal variant is built as a separate step once the portal design is decided.

Plan:
 * A separate, slimmer widget pack for the portal (only what the customer should see).
 * A shared data service (the same KPI/project queries) behind both backend and portal.
 * Access via portal users; tenant/company filtering on company_id.

The actual route is activated once the portal design is ready – kept here as a documented
starting point so we do not ship a half-finished public route.
"""
from odoo import http
from odoo.http import request


class FiqControlRoomPortal(http.Controller):

    @http.route(["/fiq/control-room/ping"], type="http", auth="user", website=False)
    def fiq_gui_control_ping(self, **kw):
        # Simple health check – confirms the module is loaded. Portal UI is built later.
        return request.make_response(
            "FIQ Control room – portal core ready (UI built as a separate step).",
            headers=[("Content-Type", "text/plain; charset=utf-8")],
        )
