/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Relations surface (H4) — the graph rendered from real Odoo data.
 *
 * Runs inside the shell slot: the frame (menu, company picker, presence) is rendered
 * once by the shell and stays put; clicking a surface swaps only this component.
 * Props arrive as {firm, har000, label} — the same shape as shell.xml:71.
 *
 * The honesty requirement, and the reason it is built in from the start:
 * a relation joins TWO parties. If one of them sits in a company the user may not see,
 * the relation does not disappear — it becomes HALF. And half a graph looks complete:
 * no empty rows, no error, just fewer nodes than reality has. So the surface counts
 * what it could not show and says so in plain words. Never present a partial graph as
 * whole.
 */
export class FiqGuiRelations extends Component {
    static template = "fiq_gui_relations.Flate";
    static props = {
        firm: { type: [Number, String], optional: true },
        har000: { type: Boolean, optional: true },
        label: { type: [String, Object], optional: true },
        "*": true,
    };

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            // "kort" first, deliberately: the card view answers who manages what and who
            // owns it, which is the question people actually arrive with. The graph
            // answers how everything hangs together, which is the follow-up.
            visning: "kort",
            laster: true,
            feil: false,
            noder: [],
            kanter: [],
            forvaltere: [],
            forvalterId: false,
            utenfor: 0,
            valgt: null,
            // Fold state is keyed on ID, never on name. In this surface that is not a
            // detail: the same contact name existing under several companies is the very
            // problem the module solves, and a property manager may share a name with a
            // property. Keying on name would collapse unrelated nodes together.
            foldet: {},
        });
        onWillStart(async () => this.hent());
    }

    async hent() {
        this.state.laster = true;
        this.state.feil = false;
        try {
            const firma = { firma_id: this.props.firm || false };
            // Both payloads in parallel: the user switches between the two views often,
            // and a second round-trip on every toggle would be felt.
            const [graf, kort] = await Promise.all([
                this.orm.call("fiq.gui.relation", "get_graf", [], firma),
                this.orm.call("fiq.gui.relation", "get_kort", [], firma),
            ]);
            this.state.noder = graf.noder || [];
            this.state.kanter = graf.kanter || [];
            this.state.forvaltere = kort.forvaltere || [];
            // The graph sees every relation; the card view only the managed ones. The
            // larger count is the honest one - it is what the user cannot see at all.
            this.state.utenfor = Math.max(graf.utenfor || 0, kort.utenfor || 0);
        } catch {
            // One broken surface must never take down the control room. A failed load
            // shows a message here; the frame and the other surfaces keep working.
            this.state.feil = true;
            this.state.noder = [];
            this.state.kanter = [];
        }
        this.state.laster = false;
    }

    byttVisning(v) {
        this.state.visning = v;
        this.state.valgt = null;
    }

    /** The manager currently shown in the card view; the first one until asked otherwise. */
    get valgtForvalter() {
        const f = this.state.forvaltere;
        if (!f.length) {
            return null;
        }
        return f.find((x) => x.id === this.state.forvalterId) || f[0];
    }

    velgForvalter(id) {
        this.state.forvalterId = id;
    }

    /** Nodes grouped by kind, so the surface reads as a list of groups rather than a blob. */
    get grupper() {
        const ut = {};
        for (const n of this.state.noder) {
            (ut[n.kind] = ut[n.kind] || { kind: n.kind, navn: n.kind_navn, noder: [] }).noder.push(n);
        }
        return Object.values(ut).sort((a, b) => a.navn.localeCompare(b.navn));
    }

    /** Explicit fold: always the same outcome, whatever state the surface is in. */
    foldAlt(fold) {
        const nytt = {};
        if (fold) {
            for (const g of this.grupper) {
                nytt[g.kind] = true;
            }
        }
        this.state.foldet = nytt;
    }

    /** Toggling fold: reflects the state where you stand. Deliberately different from foldAlt. */
    vippFold(id) {
        this.state.foldet = { ...this.state.foldet, [id]: !this.state.foldet[id] };
    }

    erFoldet(id) {
        return !!this.state.foldet[id];
    }

    velg(node) {
        this.state.valgt = this.state.valgt && this.state.valgt.id === node.id ? null : node;
    }

    /** Relations the selected node takes part in, already turned to read from its side. */
    get valgteRelasjoner() {
        if (!this.state.valgt) {
            return [];
        }
        return this.state.valgt.relasjoner || [];
    }
}

registry.category("fiq_gui_flates").add("relasjoner", {
    key: "relasjoner",
    // Plain string, and Norwegian. The shell validates this field as
    // {type: String} (fiq_gui_shell/static/src/shell.js:32), and addValidation checks
    // EVERY registered entry at once - so a dict here does not just break this surface,
    // it stops the module loader and blanks the whole interface, with a clean server log.
    // The {en_US, nb_NO} form is valid for MENU labels in the control room, which is a
    // different contract on an identically named field. Norwegian per house standard;
    // the other surfaces read "Finans", "Regnskap", "Salg".
    label: "Relasjoner",
    // Area 2 Administration. Taken from brand/fiq_fargekart_omrader.md, not chosen here:
    // the same area drifting to a different colour per surface was a real defect (KR v6.97).
    color: "#0078CC",
    sequence: 70,
    Component: FiqGuiRelations,
});
