/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { user } from "@web/core/user";
import { _t } from "@web/core/l10n/translation";

// Registry-kategorien der HVER flate registrerer innmaten sin:
//   registry.category("fiq_gui_flates").add(key, {key, label, color, sequence, Component})
const FLATE_CATEGORY = "fiq_gui_flates";

// Kontrakten HÅNDHEVES, den er ikke bare beskrevet i kommentaren over. Odoo validerer
// samme vei på sine egne registre (web/views/view.js:93, fields/field.js:65).
//
// Hvorfor: en flate med feil form (glemt Component, label som ikke er tekst) ga før en
// kryptisk feil langt inne i renderingen — eller verre, en flate som bare ikke virket.
// Nå smeller det ved registrering, med modulens egen nøkkel i meldingen.
//
// 🛑 MERK hva dette IKKE fanger: to moduler som tar SAMME nøkkel. Da kaster Odoos egen
// registry.add() en DuplicatedKeyError (core/registry.js:103) under lasting, og HELE
// grensesnittet blir blankt — med helt ren serverlogg. Det skjedde 18.07 (fiq_gui_rgs vs
// demo-flaten). Vernet mot DET ligger i demo_flates.js (viker for ekte flater) + at hver
// modul eier sin egen nøkkel. Ingen server-side test fanger den klassen feil.
// Selve oppsettet er innkapslet: addValidation validerer ALLE alt registrerte oppføringer
// med én gang (core/registry.js:202) og kaster hvis én er feil. Uten denne vakten ville en
// annen modul med feil form tatt ned HELE skallet ved lasting — altså nøyaktig den
// feilklassen valideringen skal verne mot. Vi vil ha en tydelig advarsel, ikke blank skjerm.
try {
    registry.category(FLATE_CATEGORY).addValidation({
        key: { type: String },
        label: { type: String },
        Component: { validate: (c) => c && c.prototype instanceof Component },
        color: { type: String, optional: true },
        sequence: { type: Number, optional: true },
        "*": true,
    });
} catch (e) {
    console.warn("FIQ-skall: en registrert flate bryter kontrakten —", e);
}

// Fallback-aksent når firmaet ikke har satt sin egen (samme verdi som KR bruker).
const DEFAULT_ACCENT = "#38B44A";

// Firmakode utledes av navnet KUN til visning i logo-brikka. Ingen tilgang henger på
// den — all avgrensning skjer server-side i tillatte_firmaer()/firma_domene().
function initialer(navn) {
    const ord = (navn || "").trim().split(/\s+/).filter(Boolean);
    if (!ord.length) {
        return "??";
    }
    if (ord.length === 1) {
        return ord[0].slice(0, 3).toUpperCase();
    }
    return (ord[0][0] + ord[1][0]).toUpperCase();
}

// Det DELTE V00.04-skallet. Eier chromen (presence + firma-band + sidemeny) + en slot.
export class FiqGuiShell extends Component {
    static template = "fiq_gui_shell.Shell";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            current: this.flates.length ? this.flates[0].key : false,
            firm: false,
            firms: [],
            presence: [],
            har000: false,
            theme: this._loadTheme(),
            // Skallet skal ALDRI vise oppdiktede firmaer. Får vi ikke ekte data,
            // sier vi det — tom chrome er ærligere enn feil chrome.
            error: false,
        });

        onWillStart(async () => {
            await this._load();
        });
    }

    // Ekte data fra KR (fiq_gui_control). Skallet eier ikke sikkerhet eller branding —
    // det spør KR, som avgrenser server-side. Duplisér aldri scope-logikken her.
    async _load() {
        try {
            const cfg = await this.orm.call("fiq.gui.control.config", "get_my_config", []);
            const firms = (cfg.companies || []).map((c) => ({
                id: c.id,
                navn: c.name,
                code: initialer(c.name),
                // Aksent/logo per firma hentes under; aktivt firma har dem fra get_my_config.
                color: c.id === cfg.company_id ? cfg.accent || DEFAULT_ACCENT : DEFAULT_ACCENT,
                logo: c.id === cfg.company_id ? cfg.logo || false : false,
            }));
            this.state.firms = firms;
            this.state.firm = cfg.company_id || (firms.length ? firms[0].id : false);
            this.state.har000 = !!cfg.har_000;
            this.state.error = false;
        } catch (e) {
            // Fail-closed på visningen også: ingen firmaer heller enn gale firmaer.
            this.state.firms = [];
            this.state.firm = false;
            this.state.error = _t("Could not load companies from the control room.");
        }

        try {
            this.state.presence = await this.orm.call("fiq.gui.control.config", "get_presence", []);
        } catch (e) {
            // Presence er pynt, ikke funksjon — en tom linje er greit, feil navn er ikke.
            this.state.presence = [];
        }
    }

    // Leses ved BRUK, ikke én gang i setup(). Registeret fylles av flere moduler, og
    // lasterekkefølgen mellom skallet og flatene er udefinert (de avhenger av
    // fiq_gui_control, ikke av skallet). En engangs-lesing i setup() ville låst listen
    // til det som tilfeldigvis var registrert i det øyeblikket.
    get flates() {
        return registry
            .category(FLATE_CATEGORY)
            .getAll()
            .sort((a, b) => (a.sequence || 50) - (b.sequence || 50));
    }

    get currentFlate() {
        const alle = this.flates;
        // Faller tilbake til første flate: `current` settes i setup(), da kan registeret
        // ennå være tomt. Uten dette ville skallet vist «ingen flater» selv etter at
        // modulene hadde registrert seg.
        return alle.find((f) => f.key === this.state.current) || alle[0] || false;
    }
    get currentComponent() {
        return this.currentFlate ? this.currentFlate.Component : false;
    }
    get currentFirm() {
        return (
            this.state.firms.find((f) => f.id === this.state.firm) ||
            this.state.firms[0] || { code: "", navn: "", color: DEFAULT_ACCENT, logo: false }
        );
    }

    // Klikk i sidemenyen bytter INNMAT — ikke hele siden. Det er kjernen i Vei C.
    selectFlate(key) {
        this.state.current = key;
    }

    // Firmabytte går gjennom Odoos EGEN mekanisme (user.activateCompanies) — samme vei
    // som web/webclient/switch_company_menu. Skallet finner ikke opp sin egen: da ville
    // resten av Odoo (og record rules) sett et annet aktivt firma enn skallet viste.
    async selectFirm(id) {
        if (id === this.state.firm) {
            return;
        }
        try {
            user.activateCompanies([id], { includeChildCompanies: false, reload: false });
            this.state.firm = id;
            await this._load();
        } catch (e) {
            this.state.error = _t("Could not switch company.");
        }
    }

    toggleTheme() {
        this.state.theme = this.state.theme === "dark" ? "light" : "dark";
        try {
            localStorage.setItem("fiq-theme", this.state.theme);
        } catch (e) {
            // stille — låst tema er en preferanse, ikke kritisk
        }
    }
    _loadTheme() {
        try {
            return localStorage.getItem("fiq-theme") || "light";
        } catch (e) {
            return "light";
        }
    }
}

registry.category("actions").add("fiq_gui_shell", FiqGuiShell);
