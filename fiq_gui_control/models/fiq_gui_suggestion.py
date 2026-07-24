"""📮 Forslagskasse — ønsker og forbedringer til løsningen.

Realiserer «forslagsboks»-konseptet ([[fiq-ai-devtestprod]]): forslag legges inn via den
røde postkassen i Kontrollrommet; AI/admin gjennomgår.

🔑 NORSK ER KILDESPRÅKET — engelsk er oversettelsen ([[norsk-spraklinje-er-fasit]]).
Norsk bokmål er hovedspråk i alle firmaer og alle Odoo-baser, og den norske linja er fasit
for titler, navn og etiketter. Å snu det — engelsk kilde med norsk oversettelse — ville gjort
hovedspråket til en avledning, og gitt nøyaktig den utdaterte engelske linja Gjermund har
advart mot. Samme mønster som `fiq_gui_prj` (`fiq_sjekkliste.py`: «Navn», «Nivå», «Type»).

🛑 `translate=True` på fritekstfeltene: uten den lagrer Odoo ÉN verdi for alle språk, og et
forslag skrevet på norsk kan ikke vises på engelsk for en engelsk kollega. Feltetikettene
oversettes av Odoo selv gjennom `i18n/*.po`; feltINNHOLDET krever `translate=True`.
"""

from odoo import api, fields, models


class FiqGuiSuggestion(models.Model):
    _name = "fiq.gui.suggestion"
    _description = "FIQ forslag — ønske/forbedring"
    _order = "create_date desc"

    # ── AVSENDER: menneske ELLER AI ───────────────────────────────────────────────────
    # Gjermund 24.07.2026: «det er en forslagskasse til Gjermund og AI.»
    # Begge legger inn forslag, og begge leser hverandres. Derfor holder det ikke å vite
    # HVILKEN bruker som sto bak — en AI-økt som melder et forbedringsforslag må kunne
    # skilles fra et menneske, ellers drukner de i hverandre og ingen av delene kan
    # gjennomgås for seg.
    KILDE_MENNESKE = "menneske"
    KILDE_AI = "ai"

    name = fields.Char(string="Kort tittel", required=True, translate=True)
    description = fields.Text(string="Beskrivelse", translate=True)
    category = fields.Selection(
        [
            ("onske", "Ønske"),
            ("forbedring", "Forbedring"),
            ("feil", "Feil/mangel"),
            ("annet", "Annet"),
        ],
        string="Type",
        default="onske",
        required=True,
    )
    state = fields.Selection(
        [
            ("ny", "Ny"),
            ("vurderes", "Vurderes"),
            ("planlagt", "Planlagt"),
            ("utfort", "Utført"),
            ("avslatt", "Avslått"),
        ],
        string="Status",
        default="ny",
        required=True,
    )
    # 🔑 Settes av `submit()`, aldri av brukeren — derfor `readonly`. En avsendertype
    # brukeren kan endre selv, er ikke en opplysning man kan stole på i en gjennomgang.
    kilde = fields.Selection(
        [(KILDE_MENNESKE, "Person"), (KILDE_AI, "AI")],
        string="Foreslått av (type)",
        default=KILDE_MENNESKE,
        required=True,
        readonly=True,
    )
    # Hvilken AI-økt som meldte det, i klartekst: «0.00 8.50 GUI KR (01.03)».
    # 🛑 NAVN, aldri et øktnummer alene — Gjermund har ikke noe forhold til ID-er
    # ([[feedback-names-not-ids]]).
    kilde_navn = fields.Char(string="Meldt av", readonly=True)
    user_id = fields.Many2one(
        "res.users",
        string="Bruker",
        default=lambda self: self.env.user,
        readonly=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Firma",
        default=lambda self: self.env.company,
    )

    @api.model
    def submit(self, name, description=None, category="onske", kilde=None, kilde_navn=None):
        """Opprett et forslag — fra den røde postkassen (OWL) eller fra en AI-økt.

        🔑 ÉN inngang for begge avsendere, med vilje. To separate veier ville gitt to steder
        å vedlikeholde og to måter et forslag kan se ut på. Det er feltet `kilde` som skiller
        dem, ikke hvilken metode som ble kalt.

        Ukjente verdier faller tilbake i stedet for å kaste: et forslag som går tapt fordi
        avsendertypen var feilstavet, er verre enn ett som er merket litt for forsiktig.
        Innholdet er poenget — merkelappen kan rettes etterpå.
        """
        name = (name or "").strip()
        if not name:
            return False
        gyldige_kilder = dict(self._fields["kilde"].selection)
        gyldige_kategorier = dict(self._fields["category"].selection)
        rec = self.create(
            {
                "name": name[:120],
                "description": (description or "").strip() or False,
                "category": category if category in gyldige_kategorier else "onske",
                "kilde": kilde if kilde in gyldige_kilder else self.KILDE_MENNESKE,
                "kilde_navn": (kilde_navn or "").strip()[:120] or False,
            }
        )
        return rec.id
