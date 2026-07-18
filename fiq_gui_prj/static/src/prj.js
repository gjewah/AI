/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// FIQ Prosjektoversikt — ekte innmat.
//
// Erstatter stubben som viste «Kommer». Modulen var installert, grønn og riktig registrert
// i KR-menyen, men flaten hadde ingen innmat — «installert» er ikke «ferdig» (lærdom 18.07,
// funnet av KR-sporet 01.01 som målte hele kjeden og fant at feilen lå her, ikke i menyen).
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
            // Drill: null = prosjektliste, ellers viser vi oppgavene i valgt prosjekt.
            apentProsjekt: null,
            oppgaver: [],
            lasterOppgaver: false,
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

    async velgFirma(ev) {
        const v = ev.target.value;
        this.state.valgtFirma = v ? parseInt(v, 10) : false;
        this.state.apentProsjekt = null;
        await this.last();
    }

    async apneProsjekt(p) {
        this.state.apentProsjekt = p;
        this.state.lasterOppgaver = true;
        try {
            const res = await this.orm.call(DATA, "get_oppgaver", [], {
                prosjekt_id: p.id,
                firma_id: this.state.valgtFirma || null,
            });
            this.state.oppgaver = res.oppgaver || [];
        } catch (e) {
            this.state.oppgaver = [];
        }
        this.state.lasterOppgaver = false;
    }

    tilbake() {
        this.state.apentProsjekt = null;
        this.state.oppgaver = [];
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

    // Fargen følger fremdrift, ikke pynt: rødt = ligger etter, grønt = i mål.
    fremdriftsfarge(pst) {
        if (pst >= 90) {
            return "fiq_prj_gronn";
        }
        if (pst >= 50) {
            return "fiq_prj_gul";
        }
        return "fiq_prj_rod";
    }
}

registry.category("actions").add("fiq_gui_prj_dashboard", FiqGuiPrj);
