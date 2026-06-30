#!/usr/bin/env python3
"""
Odoo module validator – kjør før push for å fange vanlige feil tidlig.
Bruk: python validate_module.py <modul-mappe>
"""
import sys
import os
import re
import ast
import py_compile
import tempfile
from xml.etree import ElementTree
from pathlib import Path

errors = []
warnings = []

def err(msg): errors.append(f"  ERROR: {msg}")
def warn(msg): warnings.append(f"  WARN:  {msg}")


def check_python(module_path):
    print("\n[1] Python-syntaks")
    for py_file in Path(module_path).rglob("*.py"):
        try:
            py_compile.compile(str(py_file), doraise=True)
        except py_compile.PyCompileError as e:
            err(f"{py_file.relative_to(module_path)}: {e}")
    if not errors:
        print("    OK")


def check_xml_syntax(module_path):
    print("\n[2] XML-syntaks")
    for xml_file in Path(module_path).rglob("*.xml"):
        try:
            ElementTree.parse(str(xml_file))
        except ElementTree.ParseError as e:
            err(f"{xml_file.relative_to(module_path)}: {e}")
    if not [e for e in errors if "xml" in e.lower()]:
        print("    OK")


def load_manifest(module_path):
    manifest_path = Path(module_path) / "__manifest__.py"
    if not manifest_path.exists():
        err("__manifest__.py mangler!")
        return {}
    with open(manifest_path, encoding="utf-8") as f:
        return ast.literal_eval(f.read())


def check_manifest_files(module_path, manifest):
    print("\n[3] Manifest-filer eksisterer")
    for key in ("data", "demo", "assets"):
        for item in manifest.get(key, []) if key != "assets" else []:
            fpath = Path(module_path) / item
            if not fpath.exists():
                err(f"Fil i manifest ikke funnet: {item}")
    # assets er dict – stier starter med modulnavn, fjern det
    module_name = Path(module_path).name
    for _, files in manifest.get("assets", {}).items():
        for f in files:
            # Strip leading module_name/ prefix
            rel = f[len(module_name)+1:] if f.startswith(module_name + "/") else f
            fpath = Path(module_path) / rel
            if not fpath.exists():
                warn(f"Asset-fil ikke funnet: {f}")
    if not [e for e in errors]:
        print("    OK")


def extract_xml_ids(xml_file):
    """Returnerer alle id= attributter definert i filen."""
    ids = set()
    try:
        tree = ElementTree.parse(str(xml_file))
        for elem in tree.iter():
            rid = elem.get("id")
            if rid:
                ids.add(rid)
    except Exception:
        pass
    return ids


def extract_refs(xml_file):
    """Returnerer alle ref('...') og ref='...' kall i filen med linjenummer."""
    refs = []
    with open(xml_file, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            # ref='...' og ref("...")
            for m in re.finditer(r"""ref\(['"]([\w.]+)['"]\)""", line):
                refs.append((lineno, m.group(1)))
            for m in re.finditer(r"""ref=['\"]([\w.]+)['\"]""", line):
                refs.append((lineno, m.group(1)))
    return refs


def check_refs(module_path, manifest):
    print("\n[4] XML ref()-validering (lasterekkefølge)")
    module_name = Path(module_path).name
    data_files = manifest.get("data", [])

    # Samle alle IDs som er kjent (med modul-prefiks)
    known_ids = set()

    # IDs fra andre moduler (base, mail etc.) – vi kan ikke sjekke disse
    external_prefixes = set(manifest.get("depends", [])) | {"base", "mail", "account"}

    for data_file in data_files:
        fpath = Path(module_path) / data_file
        if not fpath.exists():
            continue

        # Legg til IDs fra DENNE filen først (intra-fil-refs er OK)
        new_ids = extract_xml_ids(fpath)
        all_available = known_ids | new_ids

        # Sjekk referanser mot kjente IDs (inkl. denne filen)
        refs = extract_refs(fpath)
        for lineno, ref_id in refs:
            if "." in ref_id:
                prefix = ref_id.split(".")[0]
                local_id = ref_id.split(".", 1)[1]
                if prefix == module_name:
                    if local_id not in all_available and ref_id not in all_available:
                        err(f"{data_file}:{lineno} — ref '{ref_id}' ikke definert (mangler i modul?)")
                # Ekstern ref – stoler på at den finnes i avhengig modul
            elif ref_id.startswith("model_"):
                # Auto-generert modell-ref (Odoo lager ir.model.data 'model_<modell>'
                # fra Python-modellen ved registrering) – finnes alltid ved kjøretid.
                pass
            else:
                if ref_id not in all_available:
                    err(f"{data_file}:{lineno} — ref '{ref_id}' ikke definert ennå (lasterekkefølge?)")

        known_ids |= new_ids

    if not [e for e in errors if "ref" in e.lower() or "definert" in e.lower()]:
        print("    OK")


def check_depends(manifest):
    print("\n[5] Nøkkel-felt i manifest")
    for field in ("name", "version", "author", "license", "depends"):
        if not manifest.get(field):
            warn(f"Manifest mangler '{field}'")
    ver = manifest.get("version", "")
    if ver and not ver.startswith("19.0"):
        warn(f"Versjon '{ver}' starter ikke med '19.0'")
    if not manifest.get("installable"):
        warn("'installable' er ikke True")
    print("    OK" if not warnings else "")


def main():
    if len(sys.argv) < 2:
        print("Bruk: python validate_module.py <modul-mappe>")
        sys.exit(1)

    module_path = sys.argv[1]
    print(f"\n=== Validerer: {module_path} ===")

    manifest = load_manifest(module_path)

    check_python(module_path)
    check_xml_syntax(module_path)
    check_manifest_files(module_path, manifest)
    check_refs(module_path, manifest)
    check_depends(manifest)

    print("\n" + "="*50)
    if warnings:
        print("ADVARSLER:")
        for w in warnings:
            print(w)
    if errors:
        print("FEIL:")
        for e in errors:
            print(e)
        print(f"\n{len(errors)} feil funnet – fiks disse før push!")
        sys.exit(1)
    else:
        print(f"Alt OK! ({len(warnings)} advarsler)")
        sys.exit(0)


if __name__ == "__main__":
    main()
