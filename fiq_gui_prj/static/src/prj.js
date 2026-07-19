/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// FIQ Prosjektoversikt — WBS-tre med timer mot budsjett.
//
// 🔴 OMSKREVET V0.03 (2026-07-19). Forrige versjon var en LISTEVISNING: tabell over
// prosjekter -> tabell over oppgaver. Gjermund: «du har kun knapt gjenskapt listevisning
// fra Odoo NATIVE!!!» Odoo HAR allerede prosjekter i liste — den flaten ga null ny verdi.
//
// Kravspek batch 15 (docs/0.00 IQ kontrollrom_flate_spec.md, linje 195-206) ber om:
//   · WBS-tre som driller: Blokk -> Fase -> Leilighet -> Aktivitet, foldbart per nivå
//   · Per node: effektive timer / budsjett + fremdriftsbar
//   · Fargekoding på BUDSJETT-status: blå = innenfor · RØD = over budsjett · grønn = ferdig
//   · Firma-velger som små bokser øverst (049 SDVg konsern + 050/051/052/054)
//
// KANON «Odoo-native først»: flaten er et LAG. Alt den viser finnes i Odoos egne visninger;
// slås flaten av, står dataene uendret. Den oppretter ingenting og eier ingen forretningslogikk.
//
// Firma-valget sendes til serveren som en INNSNEVRING. Serveren avgjør hva som er lov
// (env.companies + record rules) — klienten kan aldri utvide sitt eget innsyn.
const DATA = "fiq.gui.prj.data";

export class FiqGuiPrj extends Component {
    static template = "fiq_gui_prj.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            laster: true,
            feil: false,
            prosjekter: [],
            firmaer: [],
            valgtFirma: false,
            // Drill: null = prosjektvalg, ellers WBS-treet for valgt prosjekt.
            apentProsjekt: null,
            tre: null,
            lasterTre: false,
            // Foldede noder, nøklet på node-ID (ikke navn — leilighetsnavn som «H0101»
            // gjentas på tvers av blokker og ville kollidert).
            foldet: {},
        });

        onWillStart(async () => {
            await this.last();
        });
    }

    async last() {
        this.state.laster = true;
        try {
            const res = await this.orm.call(DATA, "get_prosjektoversikt", [], {
                firma_id: this.state.valgtFirma || null,
            });
            this.state.prosjekter = res.prosjekter || [];
            this.state.firmaer = res.firmaer || [];
            this.state.feil = false;
        } catch (e) {
            // Ærlig tom flate framfor gale tall: si fra, ikke vis 0 som om det var sannheten.
            this.state.prosjekter = [];
            this.state.feil = _t("Could not load projects.");
        }
        this.state.laster = false;
    }

    async velgFirma(firmaId) {
        this.state.valgtFirma = firmaId;
        this.state.apentProsjekt = null;
        this.state.tre = null;
        await this.last();
    }

    async apneProsjekt(p) {
        this.state.apentProsjekt = p;
        this.state.lasterTre = true;
        this.state.tre = null;
        this.state.foldet = {};
        try {
            const res = await this.orm.call(DATA, "get_wbs_tre", [], {
                prosjekt_id: p.id,
                firma_id: this.state.valgtFirma || null,
            });
            this.state.tre = res;
        } catch (e) {
            this.state.tre = null;
            this.state.feil = _t("Could not load the work breakdown.");
        }
        this.state.lasterTre = false;
    }

    tilbake() {
        this.state.apentProsjekt = null;
        this.state.tre = null;
        this.state.foldet = {};
    }

    fold(nodeId) {
        this.state.foldet[nodeId] = !this.state.foldet[nodeId];
    }

    erFoldet(nodeId) {
        return !!this.state.foldet[nodeId];
    }

    // Flat ut treet til render-rader med dybde. OWL-maler kan ikke rekursere over
    // seg selv uten en egen underkomponent; å flate ut her gir én enkel t-foreach
    // og lar oss hoppe over foldede undertrær uten å bygge DOM vi straks skjuler.
    get rader() {
        const ut = [];
        const gaa = (noder, dybde) => {
            for (const n of noder) {
                ut.push({ node: n, dybde: dybde, harBarn: n.barn.length > 0 });
                if (n.barn.length && !this.erFoldet(n.id)) {
                    gaa(n.barn, dybde + 1);
                }
            }
        };
        if (this.state.tre) {
            gaa(this.state.tre.noder, 0);
        }
        return ut;
    }

    // ---------- visning ----------

    // Timer med norsk desimaltegn. 7.5 -> «7,5». Heltall vises uten desimal.
    timer(t) {
        const n = Math.round((t || 0) * 10) / 10;
        return (Number.isInteger(n) ? String(n) : n.toFixed(1)).replace(".", ",");
    }

    // Bredden på fremdriftsbaren klippes på 100 — men TALLET gjør det aldri.
    // Det er hele poenget: stripa er full, tallet sier 2159 %, fargen er rød.
    barBredde(pst) {
        return Math.min(100, Math.max(0, pst || 0));
    }

    statusKlasse(status) {
        return "fiq_prj_" + (status || "plan");
    }

    statusTekst(status) {
        const t = {
            over: _t("Over budget"),
            innenfor: _t("Within budget"),
            ferdig: _t("Done"),
            plan: _t("Not started"),
        };
        return t[status] || t.plan;
    }

    // Hvor mye over budsjett, i timer. Vises kun når det ER et overforbruk.
    overforbruk(node) {
        return Math.max(0, (node.forte_timer || 0) - (node.budsjett_timer || 0));
    }

    // Native-først: «Åpne i Odoo» tar brukeren til Odoos EGEN visning.
    // KR skal aldri være eneste dør inn til dataene.
    apneIOdoo(prosjektId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            name: _t("Tasks"),
            views: [[false, "list"], [false, "form"]],
            domain: [["project_id", "=", prosjektId]],
            target: "current",
        });
    }

    apneOppgave(oppgaveId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: oppgaveId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("fiq_gui_prj_dashboard", FiqGuiPrj);
