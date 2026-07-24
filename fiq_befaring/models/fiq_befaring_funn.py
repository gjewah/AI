#
# Funn / avvik / endring (befaring_module_spec, krav-utvidelse Gjermund 2026-07-01):
# bilde/avvik/endring som fanges i befaringen skal kunne dras med inn i prosjektet.
# Generisk nonconformity-linje per rom, med alvorlighet + status. company_id arves
# (related, store) fra befaringen slik at tenant-isolasjonen følger med.

from odoo import fields, models


class FiqBefaringFunn(models.Model):
    _name = "fiq.befaring.funn"
    _description = "Befaring — funn / avvik / endring"
    _order = "befaring_id, sequence, id"

    befaring_id = fields.Many2one(
        "fiq.befaring", required=True, ondelete="cascade", index=True
    )
    rom_id = fields.Many2one(
        "fiq.befaring.rom",
        ondelete="set null",
        index=True,
        help="Rommet funnet gjelder (valgfritt).",
    )
    company_id = fields.Many2one(
        related="befaring_id.company_id",
        string="Firma",
        store=True,
        index=True,
        readonly=True,
    )
    sequence = fields.Integer(string="Rekkefølge", default=10)
    name = fields.Char(
        string="Funn", required=True, help="Kort beskrivelse — navn, ikke ID."
    )
    beskrivelse = fields.Text()
    type = fields.Selection(
        [
            ("observasjon", "Observasjon"),
            ("avvik", "Avvik"),
            ("endring", "Endring"),
        ],
        default="observasjon",
        required=True,
        index=True,
    )
    alvorlighet = fields.Selection(
        [
            ("lav", "Lav"),
            ("middels", "Middels"),
            ("hoy", "Høy"),
        ],
        default="lav",
        index=True,
    )
    status = fields.Selection(
        [
            ("apen", "Åpen"),
            ("lukket", "Lukket"),
        ],
        default="apen",
        required=True,
        index=True,
    )
    foto = fields.Image(max_width=1920, max_height=1920)
