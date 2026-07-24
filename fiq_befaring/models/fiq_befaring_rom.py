#
# Rom-linje / romskjema (befaring_module_spec): per rom fanges navn/etasje/areal,
# frie tiltak, talenotat + AI-strukturerte tiltak (flerspråklig NO/EN), og hovedfoto.
# Mobil-fangst (PWA/OWL) skriver mot denne modellen; her er den generiske datastrukturen.
# company_id arves (related, store) fra befaringen → record-rule/tenant-isolasjon følger med.

from odoo import api, fields, models


class FiqBefaringRom(models.Model):
    _name = "fiq.befaring.rom"
    _description = "Befaring — rom (romskjema)"
    _order = "befaring_id, sequence, id"

    befaring_id = fields.Many2one(
        "fiq.befaring", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="befaring_id.company_id",
        string="Firma",
        store=True,
        index=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Rekkefølge", default=10)
    name = fields.Char(string="Rom", required=True, help="Romnavn — navn, ikke ID.")
    etasje = fields.Char()
    areal = fields.Float(string="Areal (m²)")
    tiltak = fields.Text(
        string="Tiltak (fritekst)",
        help="Hva som skal gjøres i rommet — fri observasjon/tiltak.",
    )
    talenotat = fields.Text(
        string="Talenotat (transkribert)",
        help="Transkribert tale fra mobil-befaring (flerspråklig råtekst).",
    )
    ai_tiltak_no = fields.Text(
        string="AI-tiltak (norsk)",
        help="AI-strukturert gjøremål på norsk (fra talenotat).",
    )
    ai_tiltak_en = fields.Text(
        string="AI-tiltak (engelsk)",
        help="AI-strukturert gjøremål på engelsk (flerspråklig lagring NO/EN).",
    )
    foto = fields.Image(max_width=1920, max_height=1920)
    funn_ids = fields.One2many("fiq.befaring.funn", "rom_id", string="Funn / avvik")

    @api.model_create_multi
    def create(self, vals_list):
        # Sørg for at funn opprettet inline også peker på befaringen (konsistens).
        recs = super().create(vals_list)
        for r in recs:
            if r.funn_ids:
                r.funn_ids.filtered(lambda f: not f.befaring_id).write(
                    {"befaring_id": r.befaring_id.id}
                )
        return recs
