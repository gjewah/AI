/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// FIQ Prosjektoversikt — PRJ-flaten.
//
// FASIT: docs/mockups/0.00 IQ prosjektoversikt_utkast03.html (artifact 87871eef),
// kartlagt ved å ÅPNE den i nettleser og KLIKKE alle 122 kontroller. Full kravspek:
// docs/0.00 IQ prj_flate_kravspek_KOMPLETT.md
//
// 🔴 HISTORIKK — hvorfor denne er skrevet om to ganger:
//   V0.02 leverte en LISTEVISNING. Gjermund: «du har kun knapt gjenskapt listevisning
//   fra Odoo NATIVE!!!» Odoo har allerede prosjekter i liste — ingen ny verdi.
//   V0.03 (jeg) leverte deretter et WBS-tre som dekket ETT av tolv elementer.
//   Begge hadde LEST specene. Å lese er ikke å se.
//
// STRUKTUREN fasiten krever:
//   3 VISNINGER (Gantt · Liste · Kanban) × 2 AKSER (Uke 7 kol · Måned 6 kol à 4 uker)
//   Alle tre tegner SAMME datasett — klienten bytter visning uten ny spørring, slik
//   fasitens renderGantt/renderListe/renderKanban leser samme TASKS-array.
//
// KANON «Odoo-native først»: flaten er et LAG. Alt den viser finnes i Odoos egne
// visninger; slås flaten av, står dataene uendret. Den oppretter ingenting.
//
// ✅ «TIL STEDE NÅ» BYGGES BEVISST IKKE HER — den eies av skallet.
// Verifisert i `fiq_gui_shell/static/src/shell.xml:6-10`: presence-linja er et FAST
// element i rammen, med ekte data fra KRs `get_presence`. Flaten vår rendres i sloten
// UNDER den. Bygde vi vår egen, ville Gjermund fått to presence-bånd som kunne vise
// ulike tall for samme øyeblikk — verre enn ett.
// (AI KRs sidemannskontroll 22.07 spurte om fraværet var bevisst. Det er det, og nå
// står det her i stedet for bare i en kommentar lenger nede.)
const DATA = "fiq.gui.prj.data";

// Tidsstatus → farge. EGEN akse fra budsjett-status (blå/rød/grønn på timer).
// Å blande dem var forvirringen mellom batch 08b (frist) og batch 15 (kost):
// en oppgave kan være i rute på tid og samtidig sprenge budsjettet.
const TID_TEKST = { rute: "I rute", folg: "Følg opp", krit: "Kritisk", plan: "Planlagt" };

export class FiqGuiPrj extends Component {
    static template = "fiq_gui_prj.Dashboard";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");

        // Skallet sender `{firm, har000, label}` (shell.xml:71). `firm` er en ekte
        // res.company-ID, brukbar rett i domener.
        //
        // 🔑 Uten dette ville firmavelgeren i KR-rammen vært død for min flate: brukeren
        // bytter firma øverst, og innholdet står uendret. Det er verre enn ingen velger —
        // han tror han ser 051 SDVp mens han ser alt.
        // 🛑 Verdien SNEVRER kun INN. Serveren avgjør hva som er lov (`env.companies` +
        // record rules); klienten kan aldri utvide sitt eget innsyn.
        const fraSkallet = this.props && this.props.firm ? parseInt(this.props.firm, 10) : false;

        // ---------- context fra AI KR (avtalt m/ AI KR 22.07) ----------
        // AI KRs lesepanel har fem knapper som peker hit: «Åpne i Prosjektoversikt»,
        // Gantt, Uke, Måned, «Oppgave i Odoo». De kaller:
        //   doAction("fiq_gui_prj.action_fiq_gui_prj",
        //            {context: {aktiv_visning: "gantt"|"liste"|"kanban",
        //                       opplosning: "uke"|"mnd", task_id: N, fra: "ai_kr"}})
        //
        // 🛑 Vi VALIDERER verdiene i stedet for å stole på dem. En ukjent visning
        // ville ellers gitt en tom flate uten feilmelding — brukeren ville sett en
        // hvit rute og ikke visst hvorfor. Ugyldig verdi faller til default.
        const ctx = (this.props && this.props.action && this.props.action.context) || {};
        const lovligVisning = ["gantt", "liste", "kanban"];
        const lovligOppl = ["uke", "mnd"];
        const ønsketVisning = lovligVisning.includes(ctx.aktiv_visning) ? ctx.aktiv_visning : "gantt";
        const ønsketOppl = lovligOppl.includes(ctx.opplosning) ? ctx.opplosning : "uke";
        // `task_id` brukes til å markere og rulle til riktig rad — ikke til å filtrere.
        // Filtrerer vi, mister brukeren konteksten han kom for å se.
        this.fraAiKr = ctx.fra === "ai_kr";
        this.markerOppgave = parseInt(ctx.task_id, 10) || false;

        // ---------- undermeny fra KR-skallet (GUI KR 23.07) ----------
        // Skallet sender valget fra hovedmenyens undermeny som prop `menyValg`.
        // Fanene «I dag / Uke / Måned / Gantt» er IKKE fire like ting — de blander
        // to akser som fasiten holder adskilt:
        //     dag/uke/mnd = OPPLØSNING   ·   gantt = VISNING
        // Derfor oversettes valget til begge aksene her, ikke bare kopieres.
        //
        // «I dag» finnes ennå ikke som egen oppløsning (fasiten har __pick(this,'day')).
        // Inntil den er bygget faller den til uke — en visning brukeren forstår, ikke
        // en tom rute. 📌 Meldt som åpen post i kartleggingen.
        //
        // 🛑 Samme validering som over: ukjent verdi ignoreres i stedet for å tas i god
        // tro. Skallet er ikke fiendtlig, men en skrivefeil i deres meny skal ikke gi
        // Gjermund en hvit skjerm uten forklaring.
        const meny = this.props && this.props.menyValg;
        const menyKart = {
            dag: { visning: "liste", opplosning: "uke" },
            uke: { visning: "liste", opplosning: "uke" },
            mnd: { visning: "liste", opplosning: "mnd" },
            gantt: { visning: "gantt", opplosning: "uke" },
        };
        const fraMeny = (meny && menyKart[meny]) || false;

        this.state = useState({
            laster: true,
            feil: false,
            // visning × oppløsning — fasitens to akser
            //
            // TRE kilder kan sette dem. Rekkefølgen er et VALG, ikke tilfeldig:
            //   1. AI KRs context  — brukeren klikket «Åpne i Gantt» på en konkret
            //                        oppgave og forventer å lande nettopp der
            //   2. undermenyen     — brukeren valgte en fane i hovedmenyen
            //   3. default         — gantt + uke
            // AI KR vinner fordi den er det MEST spesifikke ønsket: den bærer en
            // task_id og et uttrykt mål. Undermenyen er et bredere valg.
            visning: (ctx.aktiv_visning ? ønsketVisning
                : fraMeny ? fraMeny.visning : ønsketVisning),
            opplosning: (ctx.opplosning ? ønsketOppl
                : fraMeny ? fraMeny.opplosning : ønsketOppl),
            grupper: "prosjekt",    // prosjekt | rolle | ansvarlig | status | firma
            fraUke: null,
            valgtFirma: fraSkallet,
            // data
            kolonner: [],
            oppgaver: [],
            kpi: {},
            firmaer: [],
            iDag: null,
            avkortet: false,
            // Foldede grupper. Nøklet på gruppe-ID, ALDRI navn — «H0101» og
            // «Innboks» gjentas på tvers, og navn-nøkling folder urelaterte
            // grupper sammen. (Kanonisert for alle flater 19.07.)
            foldet: {},
            // AI-arbeid som prosjekt (Gjermund-direktiv 20.07)
            aiArbeid: null,
        });

        onWillStart(async () => {
            await this.last();
        });
    }

    async last() {
        this.state.laster = true;
        try {
            const res = await this.orm.call(DATA, "get_oppgaver_over_tid", [], {
                firma_id: this.state.valgtFirma || null,
                fra_uke: this.state.fraUke,
                antall: this.state.opplosning === "mnd" ? 6 : 7,
                oppløsning: this.state.opplosning,
                grupper: this.state.grupper,
            });
            this.state.kolonner = res.kolonner || [];
            this.state.oppgaver = res.oppgaver || [];
            this.state.kpi = res.kpi || {};
            this.state.firmaer = res.firmaer || [];
            this.state.iDag = res.i_dag;
            this.state.fraUke = res.fra_uke;
            this.state.avkortet = !!res.avkortet;
            this.state.feil = false;
        } catch (e) {
            // Ærlig tom flate framfor gale tall.
            this.state.oppgaver = [];
            this.state.feil = _t("Could not load tasks.");
        }
        this.state.laster = false;
    }

    // ---------- kontroller ----------

    async settVisning(v) { this.state.visning = v; }

    async settOpplosning(o) {
        if (this.state.opplosning === o) { return; }
        this.state.opplosning = o;
        await this.last();
    }

    async settGruppering(ev) {
        this.state.grupper = ev.target.value;
    }

    async velgFirma(ev) {
        const v = ev.target.value;
        this.state.valgtFirma = v ? parseInt(v, 10) : false;
        await this.last();
    }

    // Tidsnavigasjon: ett steg = ÉN kolonne. I månedsmodus er det fire uker,
    // ikke én måned — fasitens kolonner er 4-ukers bolker, ikke kalendermåneder.
    async flyttTid(retning) {
        const [aar, uke] = (this.state.fraUke || "").split("-").map(Number);
        if (!aar || !uke) { return; }
        const steg = this.state.opplosning === "mnd" ? 4 : 1;
        let nyUke = uke + retning * steg;
        let nyAar = aar;
        while (nyUke < 1) { nyAar -= 1; nyUke += 52; }
        while (nyUke > 52) { nyAar += 1; nyUke -= 52; }
        this.state.fraUke = `${nyAar}-${nyUke}`;
        await this.last();
    }

    async tilIDag() {
        this.state.fraUke = null;
        await this.last();
    }

    // ---------- kollaps: TO nivåer med bevisst ulik logikk ----------
    // «Slå sammen alle» / «Utvid alle» = EKSPLISITTE, alltid samme resultat.
    // ⊟/⊞ per gruppe = VEKSLENDE, viser tilstanden der du står.
    // 🛑 Forskjellen er tilsiktet (00.03) — ikke «rydd» den til én mekanisme.

    foldAlle() {
        const f = {};
        for (const g of this.grupper) { f[g.nokkel] = true; }
        this.state.foldet = f;
    }

    utvidAlle() { this.state.foldet = {}; }

    vekslGruppe(nokkel) {
        this.state.foldet[nokkel] = !this.state.foldet[nokkel];
    }

    erFoldet(nokkel) { return !!this.state.foldet[nokkel]; }

    // ---------- gruppering ----------

    get grupper() {
        const felt = this.state.grupper;
        const kart = new Map();

        for (const o of this.state.oppgaver) {
            let nokkel, etikett;
            if (felt === "prosjekt") {
                nokkel = `p${o.prosjekt_id}`;
                etikett = o.prosjekt;
            } else if (felt === "ansvarlig") {
                nokkel = `a${o.ansvarlig || "_ai"}`;
                etikett = o.ansvarlig || _t("AI (no assignee)");
            } else if (felt === "status") {
                nokkel = `s${o.tid_status}`;
                etikett = TID_TEKST[o.tid_status] || o.tid_status;
            } else if (felt === "firma") {
                nokkel = `f${o.firma_id}`;
                etikett = o.firma;
            } else {
                // «rolle» — fasitens eier/PL/PK/AI-ansvarlig. Rollemodellen er ikke
                // bygget ennå (fiq.project.role), så vi grupperer ærlig på det vi HAR:
                // AI-utført mot menneske-utført. Bedre enn en tom akse som lyver.
                nokkel = o.er_ai ? "r_ai" : "r_menneske";
                etikett = o.er_ai ? _t("AI") : _t("People");
            }
            if (!kart.has(nokkel)) {
                kart.set(nokkel, { nokkel, etikett, oppgaver: [] });
            }
            kart.get(nokkel).oppgaver.push(o);
        }

        // Rollup per gruppe: verste status vinner. Ellers drukner én kritisk
        // oppgave i et prosjekt som ser fint ut på toppnivå.
        const ord = { krit: 3, folg: 2, rute: 1, plan: 0 };
        return [...kart.values()].map((g) => {
            let verst = "plan";
            let fort = 0, budsjett = 0, ferdige = 0;
            for (const o of g.oppgaver) {
                if (ord[o.tid_status] > ord[verst]) { verst = o.tid_status; }
                fort += o.forte_timer;
                budsjett += o.budsjett_timer;
                if (o.ferdig) { ferdige += 1; }
            }
            return {
                ...g,
                antall: g.oppgaver.length,
                ferdige,
                tid_status: verst,
                forte_timer: Math.round(fort * 10) / 10,
                budsjett_timer: Math.round(budsjett * 10) / 10,
                budsjett_status: budsjett > 0 && fort > budsjett ? "over"
                    : ferdige === g.oppgaver.length ? "ferdig"
                    : budsjett > 0 || fort > 0 ? "innenfor" : "plan",
            };
        });
    }

    // ---------- Gantt-geometri ----------

    // Søylens plassering i prosent av tidsvinduet. Klippes i endene så en oppgave
    // som starter før vinduet fortsatt VISES — den skal ikke forsvinne bare fordi
    // brukeren har bladd fram.
    soyle(o) {
        const k = this.state.kolonner;
        if (!k.length) { return null; }
        const start = new Date(k[0].fra).getTime();
        const slutt = new Date(k[k.length - 1].til).getTime();
        const spenn = slutt - start;
        if (spenn <= 0) { return null; }

        // 🔴 PRODUCTION-FEIL RETTET 23.07: her sto `if (!o.fra) return null`.
        //
        // `fra` er `planned_date_begin` — Enterprise-planlegging. Gjermunds
        // oppgaver har den ikke utfylt; de har bare `date_deadline`. Resultatet
        // var 109 rader i Gantt UTEN en eneste søyle. Flaten så ut som den virket
        // (rader, navn, kolonner tegnet seg) og var likevel tom der det gjaldt.
        //
        // Jeg bygde mot et felt jeg antok var i bruk. Samme grunnform som
        // nøkkelfeilen: koden var riktig for en virkelighet som ikke var deres.
        //
        // 🔑 FASITEN HADDE SVARET HELE TIDEN — legenden har `▨ planlagt` som egen
        // kategori, og `24_055 Oscarsgate 20 (tilbud)` vises som en skravert boks
        // «Mulig oppstart». Uten bekreftet startdato skal oppgaven TEGNES, men
        // merkes ubekreftet. Å skjule den er å late som den ikke finnes.
        const bekreftet = !!o.fra;
        let f;
        if (bekreftet) {
            f = new Date(o.fra).getTime();
        } else if (o.frist) {
            // Ingen startdato: vis en kort, skravert boks som ender på fristen.
            // Bredden er en ANTAGELSE og skal se sånn ut — derfor stripet.
            // Vi later ikke som vi vet når arbeidet begynner.
            f = new Date(o.frist).getTime() - 3 * 86400000;
        } else {
            return null;   // verken start eller frist — ingenting å plassere
        }
        const t = o.til ? new Date(o.til).getTime()
            : (o.frist ? new Date(o.frist).getTime() : f);
        if (t < start || f > slutt) { return null; }

        const v = Math.max(0, ((f - start) / spenn) * 100);
        const h = Math.min(100, ((t - start) / spenn) * 100);
        return { venstre: v, bredde: Math.max(1.5, h - v), planlagt: !bekreftet };
    }

    // Fargeakse + evt. «planlagt»-skravering i ett. Malen skal ikke regne.
    soyleKlasse(o, s) {
        const k = this.tidKlasse(o.tid_status);
        return s && s.planlagt ? k + " fiq_prj_planlagt" : k;
    }

    fristPunkt(o) {
        const k = this.state.kolonner;
        if (!k.length || !o.frist) { return null; }
        const start = new Date(k[0].fra).getTime();
        const slutt = new Date(k[k.length - 1].til).getTime();
        const spenn = slutt - start;
        if (spenn <= 0) { return null; }
        const d = new Date(o.frist).getTime();
        if (d < start || d > slutt) { return null; }
        return ((d - start) / spenn) * 100;
    }

    get iDagStrek() {
        const k = this.state.kolonner;
        if (!k.length || !this.state.iDag) { return null; }
        const start = new Date(k[0].fra).getTime();
        const slutt = new Date(k[k.length - 1].til).getTime();
        const spenn = slutt - start;
        if (spenn <= 0) { return null; }
        const d = new Date(this.state.iDag).getTime();
        if (d < start || d > slutt) { return null; }
        return ((d - start) / spenn) * 100;
    }

    // ---------- visning ----------

    timer(t) {
        const n = Math.round((t || 0) * 10) / 10;
        return (Number.isInteger(n) ? String(n) : n.toFixed(1)).replace(".", ",");
    }

    tidKlasse(s) { return "fiq_prj_t_" + (s || "plan"); }
    budsjettKlasse(s) { return "fiq_prj_b_" + (s || "plan"); }
    tidTekst(s) { return TID_TEKST[s] || s; }

    prioSymbol(p) { return p === "h" ? "▴" : p === "l" ? "▾" : "▪"; }

    // Bredden klippes på 100 — men TALLET gjør det aldri. Det var hele feilen i
    // 1.14.0: 215,9 timer mot budsjett 10 ble vist som «100 % grønn» og skjulte
    // et 22× overforbruk.
    barBredde(pst) { return Math.min(100, Math.max(0, pst || 0)); }

    // ---------- native-først: alltid en vei ut til Odoo ----------

    // ---------- broen til AI KR (avtalt 22.07) ----------
    // Fasiten krever at broen går BEGGE veier: hver oppgaverad har et «AI KR ›»-merke,
    // og KPI «Gjort av AI» er klikkbar. Konteksten FØLGER MED — brukeren skal lande på
    // samme oppgave, ikke på en forside han må navigere seg tilbake fra.
    // AI KRs kontrakt (deres 2.14.0): {menyValg: "oppgaver"|"spor"|"konkl", task_id: N}
    apneAiKr(taskId, menyValg) {
        this.action.doAction("fiq_gui_ai_kr.action_fiq_ai_kr", {
            additionalContext: {
                menyValg: menyValg || "oppgaver",
                task_id: taskId || false,
                fra: "prj",
            },
        });
    }

    // ---------- sjekkliste fra en oppgaverad ----------
    // 🔴 FANGET AV AI KRs SIDEMANNSKONTROLL 22.07: datalaget (get_sjekklister) ble
    // bygget i 1.21.0 og meldt som levert — men var ALDRI koblet inn i flaten.
    // 0 treff på «sjekkliste» i prj.xml og prj.js. Gjermund kunne ikke nå den.
    //
    // Nøyaktig samme klasse som resten av uka: bygget riktig, aldri koblet på.
    // Jeg har kritisert andre for dette og gjorde det selv.
    //
    // Flaten (sjekkliste/sjekkliste_flate.js) er en egen klient-handling som leser
    // `active_model` + `active_id` fra context — verifisert i deres kode, linje 85-88.
    apneSjekkliste(taskId) {
        this.action.doAction({
            type: "ir.actions.client",
            tag: "fiq_sjekkliste_flate",
            name: _t("Checklists"),
            context: {
                active_model: "project.task",
                active_id: taskId,
                default_task_id: taskId,
            },
        });
    }

    apneOppgave(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    apneProsjekt(id) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "project.task",
            name: _t("Tasks"),
            views: [[false, "list"], [false, "form"]],
            domain: [["project_id", "=", id]],
            target: "current",
        });
    }

    // KPI-drill: fasitens fem kort er ALLE klikkbare og lander i Liste gruppert
    // på status. Tall som ikke kan klikkes er en blindvei.
    drillKpi(hva) {
        this.state.visning = "liste";
        this.state.grupper = "status";
        this.state.foldet = {};
        if (hva === "ai") { this.state.grupper = "rolle"; }
    }
}

registry.category("actions").add("fiq_gui_prj_dashboard", FiqGuiPrj);

// ---------- registrering i KR-skallet ----------
//
// Slot-fiksen (KR 6.95) gjør at `runAction()` bytter INNMAT i stedet for hele siden.
// Rammen — meny, firmavelger, «Til stede nå» — blir stående. Flaten bygges ÉN gang
// og virker både i KR og frittstående, fordi sloten sender samme props-form som
// skallet (`{firm, har000, label}`, jf. shell.xml:71).
//
// 🛑 KONTRAKTEN (fiq_gui_shell/static/src/shell.js:44-58) — verifisert i kilden før
// registrering, ikke antatt:
//   key       String
//   label     tekst ELLER språk-objekt {en_US, nb_NO}
//   Component må arve fra owl Component
//   color     String, valgfri
//   sequence  Number, valgfri
//
// Jeg bruker REN TEKST i `label`. Begge former er lovlige nå, men det var nettopp
// dette feltet som felte hele grensesnittet 21.07: skjemaet krevde tekst mens en
// kommentar i samme fil sa «begge former», og Relasjoner fulgte kommentaren i god tro.
// Kontrakten er rettet, men jeg velger den formen som aldri har feilet.
//
// ⚠️ `add()` kaster i KALLERENS modul (registry.js:100-101), ikke i skallet. En
// ugyldig oppføring her ville altså tatt ned MIN modul under lasting — og med den
// hele modulgrafen. Derfor er dette siste linje i fila: alt annet er ferdig definert.
// 🔴 NØKKELEN MÅ VÆRE «gui_prj», IKKE «prj» (GUI KR 23.07, verifisert i deres kode).
//
// Menyen i control_room.js:1481 kaller `runAction("gui_prj")`. Jeg registrerte «prj».
// `gui_prj` ≠ `prj` → oppslaget i `fiq_gui_flates` fant ingenting → fallback til
// `doAction` → HELE siden byttes → rammen (hovedmeny, firmavelger, «Til stede nå»)
// forsvant. Gjermunds adresse viste sju `action-`-ledd på rad: han navigerte bort,
// gjentatte ganger, i stedet for å bytte innmat.
//
// Komponenten min var altså riktig registrert hele tiden — den ble bare aldri spurt
// etter. Lærdommen: en registrering som «ser riktig ut» er verdiløs hvis nøkkelen
// ikke er DEN kalleren bruker. Samme grunnform som resten av uka: målt på ett lag,
// konkludert om et annet.
//
// 📌 `ir.actions.client` i data/fiq_gui_prj_flate.xml BEHOLDES. Kontrakten (GUI KR):
//    ir.config_parameter = AT flaten finnes (server: meny, tilgang, samlebokser)
//    fiq_gui_flates      = HVORDAN den vises (klient: komponenten)
//    `runAction` prøver sloten FØRST, `doAction` er riktig fallback for native skjermer.
//    Å fjerne den ville gjort menypunktet dødt i stedet for å åpne feil.
//
// ⚠️ Nøkkelen må være UNIK — `DuplicatedKeyError` gir blank skjerm for HELE
// grensesnittet. Verifisert ledig 23.07: registeret har finans · komm · prj ·
// regnskap · relasjoner · salg. «gui_prj» er ubrukt, og «prj» fjernes her.
registry.category("fiq_gui_flates").add("gui_prj", {
    key: "gui_prj",
    label: "Prosjekt",
    color: "#4C63D2",
    // Sequence 40 = etter AI KR (30), før tidslinje (45). Samme tall som i
    // data/fiq_gui_prj_flate.xml — de to må stemme overens, ellers står flaten ett
    // sted i menyen og et annet i skallet.
    sequence: 40,
    Component: FiqGuiPrj,

    // ── UNDERMENY: fire faner, ÉN slot (GUI KR 23.07) ──────────────────────────
    //
    // «I dag / Uke / Måned / Gantt» er FIRE FANER INNE I FLATEN, ikke fire flater.
    // De viser SAMME data i ulik oppløsning — det er en visningsbryter. Fire
    // slot-nøkler ville gitt fire menypunkter, og Gjermund 19.07: «det var aldri
    // intensjonen at det skulle være 20-30 menyer i KR.»
    //
    // Kjernen eier utseende og oppførsel; jeg leverer bare data. Bygde jeg min egen
    // meny, ville vi fått fem menyer som ser ulike ut og ikke kan foldes på tvers —
    // samme feil som de seks kollaps-implementasjonene.
    //
    // `label` som {nb_NO, en_US}: norsk før engelsk. Valget kommer tilbake som
    // prop `menyValg`, og JEG bestemmer hva det betyr.
    // `badge` = det som HASTER, ikke totalen. 0 vises ikke — settes når flaten har
    // ekte tall å melde (frister i dag), ikke som fast pynt.
    meny: [
        { key: "dag", label: { nb_NO: "I dag", en_US: "Today" } },
        { key: "uke", label: { nb_NO: "Uke", en_US: "Week" } },
        { key: "mnd", label: { nb_NO: "Måned", en_US: "Month" } },
        { key: "gantt", label: { nb_NO: "Gantt", en_US: "Gantt" } },
    ],
});
