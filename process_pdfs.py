# -*- coding: utf-8 -*-
"""
process_pdfs.py
----------------
1) Procesa PDFs en pdfs/<Fecha N>/*.PDF -> JSON en resultados/<Fecha N>/<race>.json
2) Mantiene manifiestos:
     - resultados/fechas.json
     - resultados/<Fecha N>/index.json

Uso:
  python process_pdfs.py            # procesa y actualiza manifiestos
  python process_pdfs.py --force    # reprocesa aunque exista el JSON
  python process_pdfs.py --rebuild  # NO procesa PDFs: reconstruye manifiestos desde resultados/
"""

import os, re, json, sys
from pathlib import Path
from datetime import datetime

# ===== Rutas base (Windows OK) =====
HERE = os.path.dirname(os.path.abspath(__file__))      # C:\SHOWMIDGET\TIEMPOSWEB
REPO_DIR = HERE
PDFS_DIR = os.path.join(REPO_DIR, "pdfs")
OUTPUT_DIR = os.path.join(REPO_DIR, "resultados")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===== Orden carreras para index.json =====
ORDER_MAP = {"serie": 1, "repechaje": 2, "semifinal": 3, "prefinal": 4, "final": 5}

def race_sort_key(r: str):
    m = re.match(r"([A-Za-z]+)(\d+)?$", r)
    kind = (m.group(1) if m else "").lower()
    num  = int(m.group(2) or 0)
    return (ORDER_MAP.get(kind, 99), num)

# ===== Utilidades JSON =====
def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== Normalización Fecha / Mapeo nombres =====
def normalize_fecha_folder(name: str) -> str:
    name = name.strip()
    m = re.match(r"(?i)fecha\s+(\d+)$", name, flags=re.IGNORECASE)
    if m:
        return f"Fecha {int(m.group(1))}"
    return name

def map_pdf_filename_to_race(filename: str) -> str:
    base = os.path.splitext(os.path.basename(filename))[0]
    base = base.strip().lower()
    base = re.sub(r"\s+", " ", base)

    m = re.match(r"^(serie|repechaje|semifinal)\s+(\d+)$", base, flags=re.IGNORECASE)
    if m:
        return f"{m.group(1).lower()}{int(m.group(2))}"
    if base == "prefinal": return "prefinal"
    if base == "final":    return "final"

    m2 = re.match(r"^(serie|repechaje|semifinal)(\d+)$", base, flags=re.IGNORECASE)
    if m2:
        return f"{m2.group(1).lower()}{int(m2.group(2))}"

    return "unknown"

# ===== Manifiestos =====
def update_manifests(fecha: str, race: str, out_dir: str = None):
    if out_dir is None:
        out_dir = OUTPUT_DIR

    fecha = normalize_fecha_folder(fecha)

    # fechas.json
    fechas_path = os.path.join(out_dir, "fechas.json")
    fechas = load_json(fechas_path, {"fechas": []})
    if fecha not in fechas["fechas"]:
        fechas["fechas"].append(fecha)
        fechas["fechas"].sort(key=lambda s: int(re.search(r"\d+", s).group()) if re.search(r"\d+", s) else 0)
        save_json(fechas_path, fechas)

    # index.json de la fecha
    if race and race != "unknown":
        index_path = os.path.join(out_dir, fecha, "index.json")
        index = load_json(index_path, {"races": []})
        if race not in index["races"]:
            index["races"].append(race)
            index["races"].sort(key=race_sort_key)
            save_json(index_path, index)

def rebuild_manifests_from_outputs(out_dir: str = None):
    if out_dir is None:
        out_dir = OUTPUT_DIR

    fechas = []
    for fecha_dir in sorted(Path(out_dir).glob("Fecha *")):
        if not fecha_dir.is_dir():
            continue
        fecha_name = normalize_fecha_folder(fecha_dir.name)
        json_files = [p for p in fecha_dir.glob("*.json") if p.name.lower() != "index.json"]
        if not json_files:
            continue
        fechas.append(fecha_name)

        races = sorted({p.stem for p in json_files}, key=race_sort_key)
        save_json(os.path.join(out_dir, fecha_name, "index.json"), {"races": races})

    fechas = sorted(set(fechas), key=lambda s: int(re.search(r"\d+", s).group()) if re.search(r"\d+", s) else 0)
    save_json(os.path.join(out_dir, "fechas.json"), {"fechas": fechas})

# ===== Extracción de texto de PDF =====
# Intenta pdfplumber; si no, PyPDF2
def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        import pdfplumber   # pip install pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t: text += t + "\n"
        if text.strip():
            return text
    except Exception:
        pass

    # Fallback PyPDF2
    try:
        from PyPDF2 import PdfReader  # pip install PyPDF2
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text() or ""
            if t: text += t + "\n"
    except Exception:
        return ""

    return text

# ===== Parser de líneas a filas =====
_time_re = re.compile(r"\b\d{1,2}:\d{2}(?:[.,]\d{1,3})?\b")   # 1:21.416 / 01:02,3
_int_re  = re.compile(r"^\d+$")

def _tokclean(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def _num_or_none(s: str):
    s = s.strip()
    if s in ("", "-", "—", "N/A", "n/a"): return None
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None

def _row_from_tokens(tokens):
    """
    tokens: lista de strings (separadas por 2+ espacios)
    Formato esperado (tolerante):
      pos num nombre... rec t_final laps causa...
    """
    if len(tokens) < 4:
        return None

    # Posición
    if not _int_re.match(tokens[0]): 
        return None
    pos = int(tokens[0])

    # Número
    if not _int_re.match(tokens[1]): 
        return None
    dorsal = int(tokens[1])

    # Buscar índice de tiempo (token matching pattern tiempo)
    ti = None
    for i in range(2, len(tokens)):
        if _time_re.search(tokens[i]):
            ti = i
            break
    if ti is None:
        return None

    # Nombre = tokens[2:ti-?], porque antes del tiempo puede venir recargo
    # Heurística: el token anterior al tiempo (ti-1) suele ser recargo si parece número o '-'
    rec = None
    name_end = ti
    if ti - 1 >= 2:
        maybe_rec = tokens[ti - 1]
        if maybe_rec == "-" or _num_or_none(maybe_rec) is not None:
            rec = _num_or_none(maybe_rec)
            name_end = ti - 1

    name = " ".join(tokens[2:name_end]).strip()

    t_final = tokens[ti].replace(",", ".")
    # Vtas (si hay)
    laps = None
    if ti + 1 < len(tokens) and _int_re.match(tokens[ti + 1]):
        laps = int(tokens[ti + 1])
        causa_tokens = tokens[ti + 2:]
    else:
        causa_tokens = tokens[ti + 1:]

    causa = " ".join(causa_tokens).strip() if causa_tokens else None
    causa = causa if causa and causa not in ("-", "—") else None

    return {
        "position": pos,
        "number": dorsal,
        "name": name,
        "rec": rec if rec is not None else None,
        "t_final": t_final,
        "laps": laps,
        "penalty": causa
    }

def parse_pdf_to_json(pdf_path: str):
    """
    Extrae filas robustamente del PDF. Devuelve:
      {"generated_at": "...", "source_pdf": "X.pdf", "results": [ ... ] }
    o None si no pudo encontrar ninguna fila.
    """
    text = extract_text_from_pdf(pdf_path)
    if not text.strip():
        return None

    # Normalizar líneas
    lines = []
    for raw in text.splitlines():
        line = _tokclean(raw)
        if not line:
            continue
        # filtrar cabeceras típicas
        up = line.upper()
        if ("POS" in up and "N°" in up) or ("POS" in up and "Nº" in up):
            continue
        if "POS" == up or "POS." == up:
            continue
        if up.startswith("POS "):
            continue
        lines.append(line)

    # Tokenizar por 2+ espacios, para aproximar columnas
    results = []
    for ln in lines:
        toks = re.split(r"\s{2,}", ln.strip())
        # si no separa, intentar split por 1+ espacios (casos sin alineación)
        if len(toks) < 3:
            toks = ln.split()
        row = _row_from_tokens(toks)
        if row:
            results.append(row)

    # Aceptamos resultado si hay al menos 1 fila con position y number
    results = [r for r in results if isinstance(r.get("position"), int) and isinstance(r.get("number"), int)]
    if not results:
        return None

    # Orden por posición por si vinieran desordenados
    results.sort(key=lambda r: r["position"])

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_pdf": os.path.basename(pdf_path),
        "results": results
    }

# ===== Proceso principal =====
def process_all_pdfs(force: bool = False):
    if not os.path.isdir(PDFS_DIR):
        print(f"[WARN] No existe carpeta de PDFs: {PDFS_DIR}")
        return

    total_pdfs = 0
    converted = 0
    skipped = 0
    updated_manifests = 0

    for fecha_dir in sorted(Path(PDFS_DIR).glob("Fecha *")):
        if not fecha_dir.is_dir():
            continue
        fecha_name = normalize_fecha_folder(fecha_dir.name)
        out_fecha_dir = os.path.join(OUTPUT_DIR, fecha_name)
        os.makedirs(out_fecha_dir, exist_ok=True)

        # .pdf y .PDF
        pdf_iter = list(sorted(fecha_dir.glob("*.pdf"))) + list(sorted(fecha_dir.glob("*.PDF")))
        for pdf in pdf_iter:
            total_pdfs += 1
            race = map_pdf_filename_to_race(pdf.name)
            out_json = os.path.join(out_fecha_dir, f"{race}.json")

            # saltar si existe y no forzamos
            if os.path.exists(out_json) and not force:
                print(f"[SKIP] Ya existe JSON: {out_json}")
                skipped += 1
                # mantener manifiestos coherentes
                update_manifests(fecha_name, race)
                updated_manifests += 1
                continue

            data = parse_pdf_to_json(str(pdf))
            if data is None:
                print(f"[WARN] No se pudo extraer tabla de: {pdf.name}")
                # si hubiese un json previo, al menos asegura manifiestos
                if os.path.exists(out_json):
                    update_manifests(fecha_name, race)
                    updated_manifests += 1
                continue

            # guardar JSON
            save_json(out_json, data)
            converted += 1
            print(f"[OK] JSON guardado: {out_json}")

            # manifiestos
            update_manifests(fecha_name, race)
            updated_manifests += 1

    print("\n==== RESUMEN ====")
    print(f"PDFs encontrados : {total_pdfs}")
    print(f"JSON generados   : {converted}")
    print(f"Saltados (exist.) : {skipped}")
    print(f"Manifiestos upd. : {updated_manifests}")

def main():
    args = sys.argv[1:]
    force = "--force" in args
    rebuild_only = "--rebuild" in args or "--rebuild-only" in args

    if rebuild_only:
        print("[INFO] Reconstruyendo manifiestos desde resultados/ ...")
        rebuild_manifests_from_outputs()
        print("[INFO] Listo.")
        return

    print("[INFO] Procesando PDFs y actualizando manifiestos ...")
    process_all_pdfs(force=force)
    print("[INFO] Listo.")

if __name__ == "__main__":
    main()
