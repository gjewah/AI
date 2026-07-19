/** @odoo-module **/

// FIQ AI Kontrollrom — native OWL-flate. Oppgave-oversikt (alle AI-økter: Claude Code +
// Cowork) + øktregister + org-kart. Prosjekt-filtre: skjul fullførte/kansellerte + kun kunde.
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const DATA = "fiq.gui.ai.kr.data";

export class FiqAiKontrollrom extends Component {
    static template = "fiq_gui_ai_kr.AiKr";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true, view: "oppgaver",
            skjul_ferdig: true, skjul_kansellert: true, kun_kunde: false,
            oppg: { groups: [], tot: {}, krever: [], root: "" },
            okter: [], org: { roller: [], installert: false },
            bokser: [],   // samlebokser fra hver flate — «hva haster hvor»
            spor: [],     // prosjektsporene — den VARIGE enheten (Gjermund 19.07)
        });
        onWillStart(async () => {
            // Boksene FØRST: de er Pulse-laget (kravspek: «Pulse-først, RPC-SLA <500 ms»).
            // De svarer på «hva nå?» — oppgavelista er detaljen under.
            await this.lastBokser();
            await this.lastOppgaver();
            this.state.loading = false;
        });
        // Bredden settes FØRST når boksene faktisk er tegnet — under `loading` finnes
        // ikke .bokser i DOM-en, og setProperty ville truffet ingenting.
        // Samme grep som Meldingssenteret gjør for tre-ruta (epost.js:100-102).
        onMounted(() => requestAnimationFrame(() => this.lastBoksbredde()));
    }

    async lastBokser() {
        // Hver registrert flate spørres om ETT tall-sett. Flater uten kontrakten
        // (get_kr_boks) leverer ingenting og vises ikke — ingen tomme bokser.
        try {
            this.state.bokser = await this.orm.call(DATA, "get_kr_bokser", []);
        } catch (e) {
            // En feilende boks-henting skal aldri ta ned resten av forsiden.
            this.state.bokser = [];
        }
    }

    // Klikk på en boks → åpne DEN flaten. «Trykker jeg på PRJ haster, kommer jeg til PRJ.»
    apneFlate(boks) {
        if (boks && boks.xmlid) {
            this.action.doAction(boks.xmlid);
        }
    }

    // ---- Dragbar boks-bredde (Gjermund 19.07.2026: «samme som e-post er laget») -------
    // SAMME mønster som Meldingssenteret (epost.js: BREDDER + startDrag + lastBredder,
    // 18.07.2026) — CSS-variabel + localStorage + min/max-grenser. Gjenbrukt bevisst,
    // ikke gjenoppfunnet: to flater som oppfører seg ulikt på samme handling er verre
    // enn ingen av delene.
    // Her styrer bredden hvor brede SAMLEBOKSENE er; griddet fyller resten selv.
    static BOKS = { min: 170, max: 480, std: 240, css: "--w-boks", nokkel: "fiq_ai_kr_boksbredde" };

    lastBoksbredde() {
        const rad = document.querySelector(".aikr .bokser");
        if (!rad) return;
        let v = parseInt(window.localStorage.getItem(FiqAiKontrollrom.BOKS.nokkel) || "", 10);
        if (!Number.isFinite(v)) v = FiqAiKontrollrom.BOKS.std;
        const b = FiqAiKontrollrom.BOKS;
        rad.style.setProperty(b.css, Math.min(b.max, Math.max(b.min, v)) + "px");
    }

    startDragBoks(ev) {
        const b = FiqAiKontrollrom.BOKS;
        const rad = document.querySelector(".aikr .bokser");
        if (!rad) return;
        ev.preventDefault();                                   // ingen tekstmarkering
        const start = ev.clientX;
        const fra = parseInt(getComputedStyle(rad).getPropertyValue(b.css), 10) || b.std;
        ev.target.classList.add("on");
        ev.target.setPointerCapture?.(ev.pointerId);

        const flytt = (e) => {
            const bredde = Math.min(b.max, Math.max(b.min, fra + (e.clientX - start)));
            rad.style.setProperty(b.css, bredde + "px");
        };
        const slutt = () => {
            ev.target.classList.remove("on");
            const naa = parseInt(getComputedStyle(rad).getPropertyValue(b.css), 10);
            if (Number.isFinite(naa)) {
                try { window.localStorage.setItem(b.nokkel, String(naa)); }
                catch (e) { /* privat modus e.l. — bredden gjelder da kun denne økta */ }
            }
            window.removeEventListener("pointermove", flytt);
            window.removeEventListener("pointerup", slutt);
            window.removeEventListener("pointercancel", slutt);
        };
        window.addEventListener("pointermove", flytt);
        window.addEventListener("pointerup", slutt);
        window.addEventListener("pointercancel", slutt);       // rydder også ved avbrudd
    }

    async lastOppgaver() {
        this.state.oppg = await this.orm.call(DATA, "get_ai_oppgaver", [], {
            skjul_ferdig: this.state.skjul_ferdig,
            skjul_kansellert: this.state.skjul_kansellert,
            kun_kunde: this.state.kun_kunde,
        });
    }

    async settFane(v) {
        this.state.view = v;
        if (v === "spor" && !this.state.spor.length) {
            this.state.spor = await this.orm.call(DATA, "get_spor", []);
        }
        if (v === "okter" && !this.state.okter.length) {
            this.state.okter = await this.orm.call(DATA, "get_okter", []);
        }
        if (v === "org" && !this.state.org.roller.length) {
            this.state.org = await this.orm.call(DATA, "get_org", []);
        }
    }

    async veksle(felt) {
        this.state[felt] = !this.state[felt];
        await this.lastOppgaver();
    }

    aapne(t) {
        this.action.doAction({
            type: "ir.actions.act_window", res_model: "project.task",
            res_id: t.id, views: [[false, "form"]], target: "current",
        });
    }

    tilbakeKR() { this.action.doAction("fiq_gui_control.action_fiq_gui_control"); }
}

registry.category("actions").add("fiq_ai_kr_dashboard", FiqAiKontrollrom);
