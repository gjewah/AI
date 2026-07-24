"""VERSJONSDISIPLIN — tre kontroller som fanger «installert uten aa ha kjort».

Bygget av AI KR (00.05) 24.07.2026, paa AI PKs bestilling. Kjorer paa git alene:
ingen base, ingen Odoo, ingen nettverk. Ment for port 3 i gaten.

═══ HVA DEN BESKYTTER ═══
Odoo oppgraderer en modul NAAR TALLET ENDRER SEG. Staar tallet stille, skjer
ingenting — uansett hvor mye koden er endret. Alle tre kontrollene under fanger
samme utfall: en endring som ser installert ut uten aa ha kjort.

Gjermunds regel: «versjonsnummer SIST etter hver push — saa jeg kan sjekke om
oppgraderingen faktisk skjer».

═══ 🔴 DEN ENE FELLA SOM MAA STAA I KODEN ═══
Kontroll 2 og 3 leser VERSJONSLINJA, ikke om `__manifest__.py` er blant de
endrede filene. AI PK holdt paa aa avvise funnet mitt fordi manifestet VAR
rort i alle tre tilfellene — men versjonslinja sto stille:

    adf15ee «fiq_gui_fin 19.0.1.8.1»  manifest RORT · versjon 1.8.0 -> 1.8.0

«Ble fila endret?» og «ble VERSJONEN endret?» er to spoersmaal. Det forste gir
«ja» paa alle tre. Kontrollen maa stille det andre.

═══ 🔴 tests/-FILTERET ER IKKE PYNT ═══
Kontroll 3 uten det gir 9 FALSKE av 13. En gate som gir falske treff blir slaatt
av innen en dag — og da har vi verken kontroll eller tillit. Testfiler oppgraderer
ingenting hos brukeren.
"""

import collections
import re
import subprocess
import sys

VERSJON = re.compile(r'"version"\s*:\s*"([\d.]+)"')
# Versjon nevnt i commit-emnet: «fiq_gui_fin 19.0.1.8.1: LINT» -> 19.0.1.8.1.
# Minst fire ledd, ellers treffer den datoer og tilfeldige tall.
VERSJON_I_EMNE = re.compile(r"\b(\d+\.\d+\.\d+\.\d+(?:\.\d+)?)\b")
# Mapper som faktisk kjores hos brukeren. `tests/` er BEVISST utelatt.
KJORT_KODE = ("models/", "views/", "static/", "security/", "data/", "wizards/", "report/")


def _git(*args):
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace"
    ).stdout


def _versjon(sha, sti):
    m = VERSJON.search(_git("show", f"{sha}:{sti}"))
    return m.group(1) if m else None


def _commiter(siden):
    """(sha, emne, {modul: {filer}}) for hver commit, nyeste forst."""
    ut, sha, emne, filer = [], None, None, collections.defaultdict(set)
    for linje in _git("log", f"--since={siden}", "--format=@@%H|%s", "--name-only").splitlines():
        if linje.startswith("@@"):
            if sha:
                ut.append((sha, emne, dict(filer)))
            sha, emne = linje[2:].split("|", 1)
            filer = collections.defaultdict(set)
        elif "/" in linje.strip():
            filer[linje.split("/")[0]].add(linje.strip())
    if sha:
        ut.append((sha, emne, dict(filer)))
    return ut


def kontroll_1_kollisjon(commiter):
    """To commiter setter SAMME versjon paa samme modul.

    Begge endringene overlever i git — men Odoo oppgraderer EN gang. Den som kom
    sist ser installert ut uten aa ha kjort.
    🔑 `ls-remote` for bump fanger IKKE dette: to okter kan lese samme tall i
    samme minutt og begge ta neste. Regelen virker mot sekvensiell arbeidsflyt,
    ikke mot samtidighet — derfor maa den staa her.
    """
    sett = collections.defaultdict(list)
    for sha, emne, mods in commiter:
        for mod, fs in mods.items():
            if f"{mod}/__manifest__.py" in fs and (v := _versjon(sha, f"{mod}/__manifest__.py")):
                sett[(mod, v)].append((sha[:7], emne))
    return [
        (mod, v, treff) for (mod, v), treff in sorted(sett.items()) if len(treff) > 1
    ]


def kontroll_2_logn_i_emnet(commiter):
    """Emnet lover en versjon manifestet ikke har.

    🔴 VIKTIGST AV DE TRE. Her tror alle at bumpen skjedde — den staar jo i
    loggen. Ingen leter etter en feil som er dokumentert som fikset.
    """
    funn = []
    for sha, emne, mods in commiter:
        if not (lovet := VERSJON_I_EMNE.findall(emne)):
            continue
        for mod, fs in mods.items():
            if f"{mod}/__manifest__.py" not in fs:
                continue
            faktisk = _versjon(sha, f"{mod}/__manifest__.py")
            # Modulnavnet maa staa i emnet: en commit som roerer fem moduler og
            # nevner EN versjon lyver ikke om de fire andre.
            if faktisk and mod in emne and faktisk not in lovet:
                funn.append((mod, sha[:7], emne, lovet, faktisk))
    return funn


def kontroll_3_manglende_bump(commiter):
    """Kode brukeren kjorer er endret, men VERSJONSLINJA staar stille.

    🔴 LESER VERSJONSLINJA, IKKE FILLISTA. AI PK holdt paa aa avvise funnet
    fordi manifestet VAR rort i alle tre tilfellene — men versjonen sto stille.
    Sjekker vi «ble fila endret?», slipper vi dem alle gjennom.

    🔴 tests/ EKSKLUDERT: 9 av 13 treff var testfiler, som ikke oppgraderer noe.
    """
    funn = []
    for sha, _emne, mods in commiter:
        for mod, fs in mods.items():
            kode = [
                f
                for f in fs
                if f.startswith(tuple(f"{mod}/{d}" for d in KJORT_KODE))
                and "/tests/" not in f
            ]
            if not kode:
                continue
            sti = f"{mod}/__manifest__.py"
            for_, etter = _versjon(f"{sha}~1", sti), _versjon(sha, sti)
            if for_ and etter and for_ == etter:
                funn.append((mod, sha[:7], for_, sorted(kode)))
    return funn


def main(siden="2026-07-21"):
    c = _commiter(siden)
    if not c:
        print(f"Ingen commiter siden {siden} — kontrollen maalte ingenting.")
        return 1  # tom maaling er IKKE et grontt svar

    feil = 0
    print(f"VERSJONSDISIPLIN — {len(c)} commiter siden {siden}\n")

    if t := kontroll_1_kollisjon(c):
        feil += len(t)
        print(f"[1] KOLLISJON — {len(t)} tilfelle(r): samme modul, samme versjon")
        for mod, v, treff in t:
            print(f"    {mod} {v}")
            for sha, emne in treff:
                print(f"        {sha}  {emne[:60]}")
    else:
        print("[1] KOLLISJON — ingen")

    if t := kontroll_2_logn_i_emnet(c):
        feil += len(t)
        print(f"\n[2] LOGN I EMNET — {len(t)} tilfelle(r)")
        for mod, sha, emne, lovet, faktisk in t:
            print(f"    {sha}  {mod}: emnet sier {lovet}, manifestet har {faktisk}")
            print(f"        {emne[:66]}")
    else:
        print("[2] LOGN I EMNET — ingen")

    if t := kontroll_3_manglende_bump(c):
        feil += len(t)
        print(f"\n[3] MANGLENDE BUMP — {len(t)} tilfelle(r) (tests/ ekskludert)")
        for mod, sha, v, kode in t:
            print(f"    {sha}  {mod} staar paa {v}, men endret:")
            for f in kode[:3]:
                print(f"        {f}")
            if len(kode) > 3:
                print(f"        (+{len(kode) - 3} fil(er))")
    else:
        print("\n[3] MANGLENDE BUMP — ingen")

    print(f"\n{'=' * 60}\nTOTALT: {feil} funn")
    return 1 if feil else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "2026-07-21"))
