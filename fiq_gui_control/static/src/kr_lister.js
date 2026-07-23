/** @odoo-module **/

// =============================================================================
//  KR-LISTER — de fire datadrevne seksjonene fra utkast 15
//
//  Eier: B-sporet (19.0.7.11.x). Denne fila og kr_lister.xml/.scss er MINE;
//  control_room.js/.xml/.scss eies av A-sporet og røres aldri herfra.
//
//  Fasit: `docs/mockups/0.00 IQ kontrollrom_utkast15_2026-07-20.html`, linje
//  817-851 (de tre listene) og 925-940 (periode-bøttene) — lest i kilden 23.07.
//
//  🔑 ÉN KOMPONENT, FIRE SEKSJONER. Alternativet var fire komponenter som hver
//  gjør sitt eget serverkall. Da ville forsiden fyrt av fire runder mot serveren
//  for data som uansett hentes samtidig — og seksjonene ville kommet inn i
//  tilfeldig rekkefølge mens brukeren ser på. Ett kall, ett svar, én tegning.
//
//  🛑 Radene er strukturert data fra serveren (kilde · kode · tekst · naar), ikke
//  ferdige setninger. Kolonnene MÅ holdes adskilt hele veien: smelter vi dem
//  sammen her, kan ikke stilarket justere dem mot hverandre — og fasitens
//  høyrestilte alder/tid blir umulig.
// =============================================================================

import { Component, useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

export class KrLister extends Component {
    static template = "fiq_gui_control.KrLister";
    // Kontrollrommet sender inn firmavalget og et eventuelt søkefilter. Begge er
    // valgfrie: uten dem viser komponenten alt brukeren har lov til å se.
    static props = {
        companyId: { type: [Number, Boolean], optional: true },
        sok: { type: [String, Boolean], optional: true },
    };
    static defaultProps = { companyId: false, sok: false };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            // Alle fire seksjonene starter TOMME, ikke med tall fra forrige økt.
            // En seksjon som viser gamle tall mens den laster, lyver i det halve
            // sekundet det tar — og det er nettopp da brukeren ser på den.
            krever: { totalt: 0, rader: [] },
            siste: { totalt: 0, rader: [] },
            oppgaver: { totalt: 0, filter: "", rader: [] },
            perioder: { totalt: 0, botter: [] },
            // Fold per seksjon. Alt åpent ved start — fasiten viser dem åpne.
            foldet: {},
            laster: true,
            feil: false,
        });
        onWillStart(async () => { await this.last(); });
    }

    // Oversettelse i maler: OWL kaller ikke _t direkte fra XML.
    tr(s) { return _t(s); }

    async last() {
        this.state.laster = true;
        const cid = this.props.companyId || false;
        try {
            // Fire kall i ÉN runde. Promise.all og ikke fire await-er etter
            // hverandre: sekvensielt ville forsiden ventet på summen av alle fire.
            const [krever, siste, oppgaver, perioder] = await Promise.all([
                this.orm.call("fiq.gui.control.config", "get_kr_krever_handling",
                    [], { company_id: cid }),
                this.orm.call("fiq.gui.control.config", "get_kr_siste_aktivitet",
                    [], { company_id: cid }),
                this.orm.call("fiq.gui.control.config", "get_kr_apne_oppgaver",
                    [], { company_id: cid, sok: this.props.sok || false }),
                this.orm.call("fiq.gui.control.config", "get_kr_akt_perioder",
                    [], { company_id: cid }),
            ]);
            this.state.krever = krever || { totalt: 0, rader: [] };
            this.state.siste = siste || { totalt: 0, rader: [] };
            this.state.oppgaver = oppgaver || { totalt: 0, filter: "", rader: [] };
            this.state.perioder = perioder || { totalt: 0, botter: [] };
            this.state.feil = false;
        } catch (e) {
            // Seksjonene er informasjon på en forside, aldri verdt en hvit skjerm.
            // Vi sier fra at noe feilet i stedet for å vise tomme lister som om
            // det ikke fantes noe å gjøre — en tom liste og en feilet liste ser
            // like ut for brukeren, og betyr stikk motsatt ting.
            this.state.feil = true;
        }
        this.state.laster = false;
    }

    // Fold/utvid én seksjon. Egen tilstand per seksjonsnøkkel.
    toggle(key) {
        this.state.foldet[key] = !this.state.foldet[key];
    }

    erFoldet(key) {
        return !!this.state.foldet[key];
    }

    // Klikk på en rad: åpne posten der den finnes. Rader uten model (samleraden
    // for Kommunikasjon) er ikke klikkbare — de peker ikke på ÉN post.
    aapne(rad) {
        if (!rad || !rad.model || !rad.res_id) { return; }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: rad.model,
            res_id: rad.res_id,
            views: [[false, "form"]],
            target: "current",
        });
    }
}
