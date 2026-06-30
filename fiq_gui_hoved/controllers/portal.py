# -*- coding: utf-8 -*-
"""
Portal-gjenbruk (skisse).

Hovedmeny er bygd generisk slik at KJERNEN (KPI-/widget-modellen + datakildene)
kan gjenbrukes i en portal-løsning for eksterne brukere (gratis portal-brukere, jf.
FIQ Kundeportal-mønsteret). Backend-versjonen (OWL klient-handling) er primær her;
portal-varianten bygges som eget steg når portaldesignet er bestemt.

Plan:
 * Egen, slankere widget-pakke for portal (kun det kunden skal se).
 * Felles dataservice (samme KPI-/prosjekt-spørringer) bak både backend og portal.
 * Tilgang via portal-brukere; tenant-/firma-filtrering på company_id.

Den faktiske ruten aktiveres når portaldesignet er klart – holdes som dokumentert
utgangspunkt her for å ikke skipe en halvferdig offentlig rute.
"""
from odoo import http
from odoo.http import request


class FiqHovedmenyPortal(http.Controller):

    @http.route(["/fiq/hovedmeny/ping"], type="http", auth="user", website=False)
    def fiq_gui_hoved_ping(self, **kw):
        # Enkel helsesjekk – bekrefter at modulen er lastet. Portal-UI bygges senere.
        return request.make_response(
            "FIQ Hovedmeny – portal-kjerne klar (UI bygges som eget steg).",
            headers=[("Content-Type", "text/plain; charset=utf-8")],
        )
