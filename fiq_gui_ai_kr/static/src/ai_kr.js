/** @odoo-module **/

// FIQ AI Kontrollrom — native OWL-flate. Oppgave-oversikt (alle AI-økter: Claude Code +
// Cowork) + øktregister + org-kart. Prosjekt-filtre: skjul fullførte/kansellerte + kun kunde.
import { Component, useState, onWillStart, onMounted, onWillUpdateProps } from "@odoo/owl";
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
            // Konklusjons-loggen: det Gjermund skal kunne lese OG stoppe (20.07).
            // `vis_alle_k` av som default = kanon + antatt/uverifisert, hans avgrensning.
            konkl: [], kpuls: {}, vis_alle_k: false,
        });
        onWillStart(async () => {
            // Åpne rett på en bestemt fane når kallet ber om det (`context.menyValg`
            // eller props fra en dyplenke). AI KR eier sin egen ramme og meny, så
            // dette kommer IKKE fra skallet — det er for at et menypunkt eller en
            // lenke skal kunne peke rett på f.eks. AI-konklusjoner.
            const start = this.props?.menyValg || this.props?.action?.context?.menyValg;
            if (start) {
                this.state.view = start;
            }
            // Boksene FØRST: de er Pulse-laget (kravspek: «Pulse-først, RPC-SLA <500 ms»).
            // De svarer på «hva nå?» — oppgavelista er detaljen under.
            await this.lastBokser();
            await this.lastOppgaver();
            // Åpnet skallet oss på en annen fane enn Oppgaver, må DEN fanens data hentes
            // også — ellers står brukeren i en tom visning som ser ødelagt ut.
            if (this.state.view !== "oppgaver") {
                await this.settFane(this.state.view);
            }
            this.state.loading = false;
        });
        // Skallet bytter INNMAT uten å bygge komponenten på nytt, så et menyklikk mens
        // flaten står åpen kommer som nye props — ikke som en ny `onWillStart`.
        onWillUpdateProps(async (neste) => {
            if (neste.menyValg && neste.menyValg !== this.state.view) {
                await this.settFane(neste.menyValg);
            }
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
        if (v === "konkl" && !this.state.konkl.length) {
            await this.lastKonklusjoner();
        }
    }

    // ── KONKLUSJONS-LOGGEN ──────────────────────────────────────────────────
    async lastKonklusjoner() {
        const [liste, puls] = await Promise.all([
            this.orm.call(DATA, "get_konklusjoner", [], { vis_alle: this.state.vis_alle_k }),
            this.orm.call(DATA, "get_konklusjon_puls", []),
        ]);
        this.state.konkl = liste;
        this.state.kpuls = puls;
    }

    async vekslAlleK() {
        this.state.vis_alle_k = !this.state.vis_alle_k;
        await this.lastKonklusjoner();
    }

    /** 🛑 NØDBREMSEN. Stopper UTEN begrunnelse — det er hele poenget.
     *
     *  Gjermund 21.07: «av og til må jeg bruke ordet feil for å få stoppet økter
     *  som har glemt regelen om kunstpause og starter å bygge på feil konklusjon».
     *  Derfor spør vi om begrunnelse, men lar tomt svar gå gjennom. Krevde vi tekst,
     *  ville stoppen ventet på at han rekker å formulere seg — mens økta bygger videre.
     *  Trykker han Avbryt (null), skjer ingenting; tom streng = stopp uten forklaring.
     */
    async bestrid(k) {
        const svar = window.prompt(
            `STOPP arbeidet på:\n\n«${k.konklusjon}»\n\n` +
            `Skriv hvorfor det er feil — eller la stå tomt for å stoppe med én gang.`,
            "");
        if (svar === null) return;          // avbrutt — ikke stopp noe
        k._jobber = true;
        try {
            const r = await this.orm.call(DATA, "bestrid_konklusjon", [k.id, svar || false]);
            if (r && r.ok) await this.lastKonklusjoner();
        } finally {
            k._jobber = false;
        }
    }

    async spor(k) {
        const tekst = window.prompt(`Spør om:\n\n«${k.konklusjon}»`, "");
        if (!tekst) return;                 // tomt spørsmål gir ingen mening
        await this.orm.call(DATA, "spor_om_konklusjon", [k.id, tekst]);
        await this.lastKonklusjoner();
    }

    /** Fargeaksen: hvor trygg er konklusjonen — og er den stoppet? */
    kklasse(k) {
        if (k.bestridt) return "k_bestridt";
        if (k.uten_grunnlag) return "k_umerket";
        return "k_" + (k.sikkerhet || "umerket");
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

// ══ AI KR ER ET EGET KONTROLLROM — IKKE EN FLATE INNI ET ANNET ══════════════
//
// 🔴 RETTET 22.07.2026 (Gjermund, etter å ha sett flaten i nettleser — port 7):
// «feil ramme. den skal bruke AI KR sin ramme.»
//
// 2.13.0 registrerte flaten i `fiq_gui_flates`. Det gjorde den til INNMAT i
// Kontrollrommets skall: Gjermund så KRs meny, KRs «Til stede nå», KRs firmavelger
// og knappen «Tilbake til Kontrollrommet» — mens AI KR bare var innholdet inni.
// AI KR har SIN EGEN ramme (`.top` + `.brand` i ai_kr.xml). Den ble aldri vist.
//
// 🔑 HVORFOR REGISTRERINGEN LIKEVEL SÅ RIKTIG UT: `fiq_gui_control` meldte at
// flaten «kaster brukeren ut av rammen», og skall-registrering ER riktig svar —
// for en FLATE. AI KR er ikke en flate; det er et sidestilt kontrollrom.
// Riktig løsning på deres observasjon var aldri å underordne AI KR skallet.
//
// ⚠️ MEKANISMEN SOM BEHOLDES: `ir.config_parameter` i data/ gir AI KR en DØR i
// KR-menyen, og `ir.actions.client` åpner den med sin EGEN ramme. Det er de to
// mekanismene som skal virke sammen her — ikke skall-registreringen.
// (Kanonisert skille, AI PK 18.07: KR-MENY ≠ SKALL. Blandes de, forsvinner rammen.)
