#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Parser de "Posiciones en el campeonato cumplidas N fechas" -> posiciones.json
# - Reúne SOLO los bloques cuyo encabezado contiene exactamente "cumplidas ... fechas".
# - Acumula filas a lo largo de varias páginas (hasta ~104 corredores).
# - Evita duplicados por (pos, nro, nombre).
# - Backfill de columnas numéricas para tolerar pequeños cambios de layout.
#
# Uso sugerido (Windows):
#   python parse_posiciones.py FECHA10.pdf --out posiciones.json --pretty --dump-text debug_pos.txt --dump-candidates cand.txt
#
import argparse, json, os, re, shutil, subprocess, sys
from datetime import datetime, timezone

# 1) Utilidades ----------------------------------------------------------------
NUM_TOKEN = re.compile(r'^\d+(?:[.,]\d+)?$')

def to_float(s: str):
    if s is None: return None
    s = s.strip()
    if not s: return None
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None

def call_pdftotext(pdf_path: str):
    if not shutil.which("pdftotext"):
        return None
    try:
        out = subprocess.check_output(
            ["pdftotext", "-layout", "-enc", "UTF-8", pdf_path, "-"],
            stderr=subprocess.STDOUT
        )
        return out.decode("utf-8", errors="replace")
    except Exception:
        return None

def fallback_pdfminer(pdf_path: str):
    try:
        from pdfminer.high_level import extract_text
    except Exception as e:
        raise RuntimeError("Falta pdfminer.six (pip install pdfminer.six)") from e
    return extract_text(pdf_path)

# 2) Detección de encabezados “cumplidas N fechas” -----------------------------
HDR = re.compile(
    r'Posiciones\s+en\s+el\s+campeonato\s+cumplidas?\s+(\d+)\s+fechas?',
    flags=re.I
)

# Líneas de cabecera de columnas típicas (tolerante)
IS_COL_HEADER = re.compile(r'^\s*Pos\.?\s+N(ro|º|°|o)?\b', flags=re.I)

# Candidatas de fila: pos nro ...
ROW_CANDIDATE = re.compile(r'^\s*(\d{1,3})\s+(\d{1,3})\s+(.+)$')

def tokenize_layout(line: str):
    parts = re.split(r'\s{2,}', line.strip())
    if len(parts) <= 2:
        parts = re.split(r'\s+', line.strip())
    return [p for p in parts if p != '']

def parse_row(line: str):
    m = ROW_CANDIDATE.match(line)
    if not m: 
        return None
    try:
        pos = int(m.group(1)); nro = int(m.group(2))
    except:
        return None
    tail = m.group(3).rstrip()
    cols = tokenize_layout(tail)

    # Nombre hasta primer token numérico
    name_tokens = []
    j = 0
    while j < len(cols) and not NUM_TOKEN.match(cols[j]):
        name_tokens.append(cols[j]); j += 1
    nombre = " ".join(name_tokens).strip()

    # Números restantes
    nums, rest_tokens = [], []
    for k in range(j, len(cols)):
        if NUM_TOKEN.match(cols[k]):
            nums.append(to_float(cols[k]))
        else:
            rest_tokens.append(cols[k])

    # Backfill desde la cola numérica: [total, final, prefinal, semif, serie, anterior]
    anterior = serie = semif = prefinal = final = total = None
    if len(nums) >= 1: total    = nums[-1]
    if len(nums) >= 2: final    = nums[-2]
    if len(nums) >= 3: prefinal = nums[-3]
    if len(nums) >= 4: semif    = nums[-4]
    if len(nums) >= 5: serie    = nums[-5]
    if len(nums) >= 6: anterior = nums[-6]

    # Fin: entero suelto en tokens resto o al final de la línea
    fin = None
    for tok in rest_tokens:
        if re.fullmatch(r'\d{1,2}', tok):
            try: fin = int(tok); break
            except: pass
    if fin is None:
        mfin = re.search(r'(\d{1,2})\s*$', line)
        if mfin:
            try: fin = int(mfin.group(1))
            except: fin = None

    extras_raw = " ".join(rest_tokens).strip() or None

    return {
        "pos": pos, "nro": nro, "nombre": nombre,
        "anterior": anterior, "serie": serie, "semif": semif,
        "prefinal": prefinal, "final": final, "total": total,
        "fin": fin, "extras_raw": extras_raw
    }

# 3) Extractor de bloques “cumplidas N fechas” --------------------------------
def extract_blocks(full_text: str):
    """Devuelve lista de (n_fechas, texto_del_bloque). Un bloque se extiende hasta:
       - el próximo encabezado 'cumplidas N fechas', o
       - 'Detalle de puntos', o
       - fin del documento.
    """
    blocks = []
    matches = list(HDR.finditer(full_text))
    for i, m in enumerate(matches):
        n_fechas = int(m.group(1))
        start = m.end()
        if i + 1 < len(matches):
            end = matches[i+1].start()
        else:
            # intentar cortar por "Detalle de puntos" si aparece más adelante
            tail = full_text[start:]
            cut = re.search(r'(?:\n|\r)Detalle\s+de\s+puntos', tail, flags=re.I)
            end = start + cut.start() if cut else len(full_text)
        block_text = full_text[start:end]
        blocks.append((n_fechas, block_text))
    return blocks

# 4) Parseo de filas SOLO dentro de esos bloques --------------------------------
def parse_rows_in_block(block_text: str):
    lines = block_text.splitlines()
    rows, candidates = [], []
    in_table = False
    for ln in lines:
        s = ln.strip()
        if not s: 
            continue
        if not in_table:
            # Activar cuando encontremos cabecera de columnas o una primer fila clara
            if IS_COL_HEADER.match(s) or ROW_CANDIDATE.match(s):
                in_table = True
            else:
                continue
        # Saltar cabeceras y separadores
        if IS_COL_HEADER.match(s) or re.match(r'^[-–_]{3,}$', s):
            continue
        if ROW_CANDIDATE.match(s):
            candidates.append(ln)
            row = parse_row(ln)
            if row:
                rows.append(row)
        # Cortes duros del bloque
        if re.match(r'^(?:Detalle\s+de\s+puntos)\b', s, flags=re.I):
            break
    return rows, candidates

# 5) Main ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Extrae SOLO 'Posiciones en el campeonato cumplidas N fechas'")
    ap.add_argument("pdf", help="Ruta al PDF (ej: FECHA10.pdf)")
    ap.add_argument("--out", default="posiciones.json", help="Archivo JSON de salida")
    ap.add_argument("--pretty", action="store_true", help="Indentación legible")
    ap.add_argument("--dump-text", default=None, help="Guardar texto completo extraído en .txt")
    ap.add_argument("--dump-candidates", default=None, help="Guardar líneas candidatas en .txt")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"[ERROR] No existe: {args.pdf}", file=sys.stderr); sys.exit(2)

    text = call_pdftotext(args.pdf)
    if text is None:
        text = fallback_pdfminer(args.pdf)

    if args.dump_text:
        with open(args.dump_text, "w", encoding="utf-8") as f:
            f.write(text)

    blocks = extract_blocks(text)
    if not blocks:
        print("[ADVERTENCIA] No se detectaron bloques 'cumplidas N fechas'.", file=sys.stderr)

    all_rows = []
    all_candidates = []
    fechas_set = set()
    for n_fechas, block_text in blocks:
        fechas_set.add(n_fechas)
        rows, cands = parse_rows_in_block(block_text)
        all_rows.extend(rows)
        all_candidates.extend(cands)

    # Deduplicar por (pos, nro, nombre)
    seen = set()
    uniq_rows = []
    for r in all_rows:
        key = (r.get("pos"), r.get("nro"), (r.get("nombre") or "").lower())
        if key not in seen:
            seen.add(key); uniq_rows.append(r)

    if args.dump_candidates:
        with open(args.dump_candidates, "w", encoding="utf-8") as f:
            f.write("\n".join(all_candidates))

    # Elegir la mayor cantidad de fechas cumplidas (por si hubieran varias)
    fechas_cumplidas = max(fechas_set) if fechas_set else None

    meta = {
        "source_pdf": os.path.basename(args.pdf),
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fechas_cumplidas": fechas_cumplidas,
        "fechas_detectadas": sorted(list(fechas_set)) if fechas_set else []
    }

    data = {"meta": meta, "standings": uniq_rows}

    with open(args.out, "w", encoding="utf-8") as f:
        if args.pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"[OK] Escribí {args.out} con {len(uniq_rows)} filas.")
    if args.dump_candidates:
        print(f"[INFO] Guardé líneas candidatas en: {args.dump_candidates}")
    if fechas_cumplidas is not None:
        print(f"[INFO] Fechas cumplidas detectadas: {fechas_cumplidas}")

if __name__ == "__main__":
    main()
