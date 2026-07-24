#
# Meldingssenter V00.04 – referanse-visning.
# Serverer den GODKJENTE mockupen (docs/mockups/meldingssenter_v0104.html) som en
# selvstendig side, slik at OWL-klienthandlingen kan vise den isolert i en <iframe>.
# Hensikt: en LEVENDE V00.04-referanse i Odoo å vurdere mot dagens KR (v6.7x) – jf.
# beslutnings-notatet "Skal V00.04 bli KR-master?" (Alt C, gradvis).
# Native OWL-port + ekte data kommer i vNext etter master-beslutningen.

from odoo import http
from odoo.http import request
from odoo.tools.misc import file_open

_MOCKUP_REL = "fiq_gui_epost/static/v0104/meldingssenter_v0104.html"

# Egen, avgrenset CSP for DENNE ruten: mockupen har inline <style>/<script> + data:-logoer.
# Isolert i iframe → påvirker ikke Odoo-backendens egen policy.
_CSP = (
    "default-src 'self' 'unsafe-inline' data: blob:; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self' 'unsafe-inline'; "
    "frame-ancestors 'self';"
)


class FiqMeldingssenterRef(http.Controller):
    @http.route(
        "/fiq_gui_epost/v0104",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def meldingssenter_v0104(self, **kw):
        with file_open(_MOCKUP_REL, "r") as fh:
            body = fh.read()

        # Pakk inn i et komplett HTML-dokument hvis mockupen er et fragment.
        if body.lstrip().lower().startswith("<!doctype"):
            html = body
        else:
            html = (
                "<!doctype html><html lang='no'><head>"
                "<meta charset='utf-8'>"
                "<meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Meldingssenter V00.04</title></head><body>"
                + body
                + "</body></html>"
            )

        return request.make_response(
            html,
            headers=[
                ("Content-Type", "text/html; charset=utf-8"),
                ("Content-Security-Policy", _CSP),
                ("X-Frame-Options", "SAMEORIGIN"),
            ],
        )
