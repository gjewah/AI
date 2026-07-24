from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    # Merkevare per firma i Kontrollrommet. Generisk: alle firmaer deler den samme
    # mørkegrå sidemenyen; bare aksentfargen og logoen varierer.
    #
    # 🔑 NORSK ER KILDESPRÅKET — engelsk er oversettelsen ([[norsk-spraklinje-er-fasit]]).
    # Etikettene sto på engelsk fram til 24.07.2026, en rest etter 18→19-oppgraderingen.
    # De VIRKET (nb_NO.po hadde treff på alle), men brøt husregelen: norsk bokmål er
    # hovedspråk i alle baser, og den norske linja er fasit. Er engelsk kilden, blir norsk
    # en avledning — og en engelsk streng ingen har rørt på år blir sannheten koden leser.
    fiq_control_accent = fields.Char(
        string="Aksentfarge i Kontrollrommet",
        default="#38B44A",
        help="Hex-farge brukt som aksent i Kontrollrommet (aktiv meny, nøkkeltall, fremdrift).",
    )
    fiq_control_logo = fields.Binary(
        string="Logo i Kontrollrommet (lys variant)",
        help="Logo som vises i Kontrollrommets topplinje og sidemeny. Bruk en variant som er "
        "lesbar mot mørk bakgrunn (hvit/sølv) til sidemenyen.",
    )
    fiq_control_as_home = fields.Boolean(
        string="Start i Kontrollrommet",
        default=False,
        help="Slått PÅ: interne brukere i dette firmaet får Kontrollrommet som startside. "
        "Slått AV: brukerne beholder eller får tilbake Odoos standard startside. "
        "Styres av administrator — slå på først når flaten er verifisert stabil.",
    )
