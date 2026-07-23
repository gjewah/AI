/** @odoo-module **/

/**
 * FIQ Sjekkliste-flate — OWL-sprettopp over fiq.sjekkliste / fiq.sjekkliste.punkt.
 *
 * KANON «Odoo-native først» (Gjermund 2026-07-16): dette er en PENERE INNGANG til de
 * samme dataene som Odoos egne visninger — ikke lagringen. Slås flaten av, står feltene
 * fortsatt (verifisert: liste/skjema/søk + fane på oppgaven finnes native).
 *
 * TO MODUSER over ÉN komponent (Gjermund: «to flater — PC-eier legger til / mobil-arbeider
 * kvitterer»):
 *   • bygg     — intern eier: lag/rediger punkter, sett krav (📄 dok / 📷 foto / ✍ signatur)
 *   • kvitter  — arbeider/UE: huk av utført, last opp foto/dok, signér. Store trykkflater.
 * Modus defaulter fra `user.isInternalUser` (arbeider = portal → kvitter), men er togglebar
 * så en byggeleder på mobil også kan kvittere.
 *
 * RETTIGHETSNØYTRAL: flaten innfører INGEN ny res.groups. Den leser/skriver kun eksisterende
 * data via ORM og arver security fra ir.model.access.csv (intern = CRUD, portal = les liste +
 * skriv punkt). Rolle-motoren (00.03gew) eier rettighetsmodellen — meldt i koordineringsfila.
 *
 * KRAV-CONSTRAINT: modellen hindrer «utført» før alle krav er levert (_sjekk_krav_for_utfoert).
 * Flaten stiller ALDRI stille — feiler et forsøk, vises modellens ValidationError som varsel,
 * og «venter på»-teksten (mangler) står ved punktet. Aldri skjul en feil.
 *
 * Opplasting: kjernens FileInput → /web/binary/upload_attachment (resModel/resId) skaper en
 * ir.attachment knyttet til punktet, returnerer dens id → skrives i kvitt_foto_id/kvitt_dok_id.
 * Ingen egen base64-håndtering (verifisert mot web/static/src/core/file_input/file_input.js).
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { FileInput } from "@web/core/file_input/file_input";
import { _t } from "@web/core/l10n/translation";

const PUNKT_FELT = [
    "name", "beskrivelse", "sequence",
    "krav_dok", "krav_foto", "krav_sign",
    "utfoert", "kan_kvitteres", "mangler",
    "kvitt_dok_id", "kvitt_foto_id",
    "kvitt_sign_av", "kvitt_sign_dato", "kvitt_av", "kvitt_dato",
];
const LISTE_FELT = [
    "name", "nivaa", "type_liste", "task_id", "project_id",
    "versjon", "antall_ok", "antall_punkt", "fremdrift", "company_id",
];

export class FiqSjekklisteFlate extends Component {
    static template = "fiq_gui_prj.SjekklisteFlate";
    static components = { FileInput };
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            lister: [],          // sjekklistene i scope
            valgtId: null,       // aktiv sjekkliste
            punkter: [],         // punktene på den aktive lista
            modus: "kvitter",    // "bygg" | "kvitter"
            laster: true,
            nyPunktNavn: "",
        });

        onWillStart(async () => {
            // Modus fra rolle: intern eier bygger, arbeider (portal) kvitterer.
            this.state.modus = user.isInternalUser ? "bygg" : "kvitter";
            await this.lastLister();
        });
    }

    // ── Kontekst fra client action: åpne direkte på én oppgave/liste ──────────
    get ctx() {
        return (this.props.action && (this.props.action.context || {})) || {};
    }

    async lastLister() {
        this.state.laster = true;
        const c = this.ctx;
        const domain = [];
        // Åpnet fra en oppgave? Vis kun den oppgavens lister.
        if (c.active_model === "project.task" && c.active_id) {
            domain.push(["task_id", "=", c.active_id]);
        } else if (c.default_task_id) {
            domain.push(["task_id", "=", c.default_task_id]);
        }
        const lister = await this.orm.searchRead(
            "fiq.sjekkliste", domain, LISTE_FELT, { order: "id desc" }
        );
        this.state.lister = lister;
        if (lister.length) {
            await this.velgListe(c.default_sjekkliste_id || lister[0].id);
        } else {
            this.state.valgtId = null;
            this.state.punkter = [];
        }
        this.state.laster = false;
    }

    async velgListe(id) {
        this.state.valgtId = id;
        await this.lastPunkter();
    }

    async lastPunkter() {
        if (!this.state.valgtId) {
            this.state.punkter = [];
            return;
        }
        this.state.punkter = await this.orm.searchRead(
            "fiq.sjekkliste.punkt",
            [["sjekkliste_id", "=", this.state.valgtId]],
            PUNKT_FELT,
            { order: "sequence, id" }
        );
    }

    get valgtListe() {
        return this.state.lister.find((l) => l.id === this.state.valgtId) || null;
    }

    settModus(m) {
        this.state.modus = m;
    }

    // ── KVITTER-modus ────────────────────────────────────────────────────────
    async vekslUtfoert(punkt) {
        // Modellen har en constraint: utført krever alle leverte krav. Vi lar den
        // håndheve — feiler den, viser vi grunnen, ikke en stille no-op.
        const nyVerdi = !punkt.utfoert;
        try {
            await this.orm.call("fiq.sjekkliste.punkt", "write", [[punkt.id], {
                utfoert: nyVerdi,
                // Ved utkryssing: stemple hvem/når. Ved angring: la stemplene stå (historikk).
                ...(nyVerdi ? { kvitt_av: user.name, kvitt_dato: this._naa() } : {}),
            }]);
            await this.lastPunkter();
            await this.oppdaterListeHode();
        } catch (e) {
            // ValidationError fra modellen («venter dokument + foto») → vis den, behold tilstand.
            this.notification.add(this._feilTekst(e), { type: "warning", sticky: false });
            await this.lastPunkter();
        }
    }

    async signer(punkt) {
        const navn = user.isInternalUser ? user.name : (await this._sporNavn());
        if (!navn) {
            return;
        }
        await this.orm.call("fiq.sjekkliste.punkt", "write", [[punkt.id], {
            kvitt_sign_av: navn,
            kvitt_sign_dato: this._naa(),
        }]);
        await this.lastPunkter();
    }

    // FileInput-callback: attachment er alt skapt og knyttet til punktet (resModel/resId).
    // Vi skriver bare dens id inn i riktig kvitterings-felt.
    async etterOpplasting(felt, parsed) {
        const data = Array.isArray(parsed) ? parsed[0] : parsed;
        if (!data || !data.id) {
            this.notification.add(_t("Opplastingen ga ingen fil."), { type: "danger" });
            return;
        }
        const punktId = this._sisteOpplastPunkt;
        if (!punktId) {
            return;
        }
        await this.orm.call("fiq.sjekkliste.punkt", "write", [[punktId], {
            [felt]: data.id,
        }]);
        await this.lastPunkter();
    }

    // FileInput trenger resId = punktet. Vi husker hvilket punkt knappen gjelder.
    forberedOpplasting(punktId) {
        this._sisteOpplastPunkt = punktId;
    }

    // ── BYGG-modus (kun intern eier) ─────────────────────────────────────────
    async leggTilPunkt() {
        const navn = (this.state.nyPunktNavn || "").trim();
        if (!navn || !this.state.valgtId) {
            return;
        }
        const nesteSeq = 10 + this.state.punkter.length * 10;
        await this.orm.create("fiq.sjekkliste.punkt", [{
            sjekkliste_id: this.state.valgtId,
            name: navn,
            sequence: nesteSeq,
        }]);
        this.state.nyPunktNavn = "";
        await this.lastPunkter();
        await this.oppdaterListeHode();
    }

    async vekslKrav(punkt, felt) {
        await this.orm.call("fiq.sjekkliste.punkt", "write", [[punkt.id], {
            [felt]: !punkt[felt],
        }]);
        await this.lastPunkter();
    }

    async slettPunkt(punkt) {
        await this.orm.call("fiq.sjekkliste.punkt", "unlink", [[punkt.id]]);
        await this.lastPunkter();
        await this.oppdaterListeHode();
    }

    async oppdaterListeHode() {
        // Fremdrift/antall er compute+store på lista — les dem friskt så hodet stemmer.
        if (!this.state.valgtId) {
            return;
        }
        const [oppd] = await this.orm.read(
            "fiq.sjekkliste", [this.state.valgtId],
            ["antall_ok", "antall_punkt", "fremdrift", "versjon"]
        );
        const l = this.state.lister.find((x) => x.id === this.state.valgtId);
        if (l && oppd) {
            Object.assign(l, oppd);
        }
    }

    // ── Hjelpere ─────────────────────────────────────────────────────────────
    _naa() {
        // Odoo forventer «YYYY-MM-DD HH:MM:SS» (UTC) for Datetime-felt via ORM.
        return luxon.DateTime.utc().toFormat("yyyy-MM-dd HH:mm:ss");
    }

    async _sporNavn() {
        // Arbeider uten Odoo-navn signerer med fritekst.
        return window.prompt(_t("Signér som (navn):")) || "";
    }

    _feilTekst(e) {
        const raw =
            (e && e.data && e.data.message) ||
            (e && e.message) ||
            _t("Kunne ikke kvittere ut punktet.");
        return raw;
    }

    // Etiketter for nivå/type (menneskelig, norsk).
    kravIkon(punkt) {
        const k = [];
        if (punkt.krav_dok) k.push("📄");
        if (punkt.krav_foto) k.push("📷");
        if (punkt.krav_sign) k.push("✍");
        return k.join(" ");
    }
}

registry.category("actions").add("fiq_sjekkliste_flate", FiqSjekklisteFlate);
