# coding: utf-8
import os, re, json
from pathlib import Path

import pdfplumber

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from pdf2image import convert_from_path
    import pytesseract
except Exception:
    convert_from_path = None
    pytesseract = None

# ==== CONFIG ====
PDF_DIR = "./pdfs"
OUTPUT_DIR = "./resultados"
DEBUG_DIR = os.path.join(OUTPUT_DIR, "_debug")
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(DEBUG_DIR, exist_ok=True)

# Opcional (Windows): seteá si tu sistema no los encuentra solo
TESSERACT_CMD = None  # r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = None   # r"C:\poppler\Library\bin"
if pytesseract and TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

OCR_DPI = 300
MIN_TOKENS_THRESHOLD = 25  # si hay menos, intentamos siguiente extractor

# ==== Manifiestos (fechas.json e index.json) ====
ORDER_MAP = {"serie": 1, "repechaje": 2, "semifinal": 3, "prefinal": 4, "final": 5}

def race_sort_key(r: str):
    m = re.match(r"([A-Za-z]+)(\d+)?$", r)
    kind = (m.group(1) if m else "").lower()
    num  = int(m.group(2) or 0)
    return (ORDER_MAP.get(kind, 99), num)

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

def update_manifests(fecha_dir: str, race: str):
    """
    Asegura que:
      - resultados/fechas.json contenga 'Fecha N'
      - resultados/Fecha N/index.json contenga 'race'
    (Durante el procesado. Luego se hace un rebuild global que “limpia”.)
    """
    fechas_path = os.path.join(OUTPUT_DIR, "fechas.json")
    fechas = load_json(fechas_path, {"fechas": []})
    if fecha_dir not in fechas["fechas"]:
        fechas["fechas"].append(fecha_dir)
        fechas["fechas"].sort(key=lambda s: int(re.search(r"\d+", s).group()) if re.search(r"\d+", s) else 0)
        save_json(fechas_path, fechas)

    if race and race != "unknown":
        index_path = os.path.join(OUTPUT_DIR, fecha_dir, "index.json")
        index = load_json(index_path, {"races": []})
        if race not in index["races"]:
            index["races"].append(race)
            index["races"].sort(key=race_sort_key)
            save_json(index_path, index)

# === Utilidades de normalización ===
def norm(s: str) -> str:
    if s is None: return ""
    s = s.replace("\u00A0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()

def is_time_token(tok: str) -> bool:
    if not tok: return False
    t = tok.replace(",", ".")
    return bool(re.match(r"^\d{1,2}[:.]\d{2}([.,]\d{2,3})?$", t))

def join_time_tokens(tokens_line):
    """Une tokens tipo 1:21 . 416 -> 1:21.416 y 1 : 21 , 416 -> 1:21,416."""
    out = []
    i = 0
    while i < len(tokens_line):
        cur = tokens_line[i]["text"]
        if i+2 < len(tokens_line):
            nxt = tokens_line[i+1]["text"]
            nxt2 = tokens_line[i+2]["text"]
            if re.fullmatch(r"[:\.,]", nxt) and re.fullmatch(r"\d{2,3}", nxt2) and re.fullmatch(r"\d{1,2}[:.]\d{2}", cur.replace(" ", "")):
                merged = (cur + nxt + nxt2).replace(" ", "")
                tokens_line[i]["text"] = merged
                i += 3
                out.append(tokens_line[i-3])
                continue
        out.append(tokens_line[i])
        i += 1
    return out

def clean_time_str(s):
    if not s: return None
    s = s.strip()
    if s.upper() in {"N/C","NC","DNS","DNF"}: return None
    if s in {"99:99.999","99:99,999"}: return None
    return s

def time_to_seconds(s):
    s = clean_time_str(s)
    if not s: return None
    s = s.replace(",", ".")
    if ":" not in s and "." in s:
        s = s.replace(".", ":", 1)
    m = re.match(r"^(\d{1,2}):(\d{2})(?:[.,](\d{2,3}))?$", s)
    if not m: return None
    mm = int(m.group(1))
    ss = int(m.group(2))
    ms = m.group(3)
    frac = float(f"0.{ms}") if ms else 0.0
    return mm*60 + ss + frac

# === Extracción de TOKENS con coordenadas ===
def tokens_pdfplumber(pdf_path):
    toks = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pidx, page in enumerate(pdf.pages):
                for w in page.extract_words(use_text_flow=True) or []:
                    toks.append({
                        "page": pidx,
                        "x": float(w["x0"]), "y": float(w["top"]),
                        "w": float(w["x1"] - w["x0"]), "h": float(w["bottom"] - w["top"]),
                        "text": norm(w["text"])
                    })
    except Exception:
        pass
    return toks, "pdfplumber"

def tokens_pymupdf(pdf_path):
    if not fitz: return [], "pymupdf"
    toks = []
    try:
        with fitz.open(pdf_path) as doc:
            for pidx, page in enumerate(doc):
                for b in page.get_text("words") or []:
                    toks.append({
                        "page": pidx,
                        "x": float(b[0]), "y": float(b[1]),
                        "w": float(b[2]-b[0]), "h": float(b[3]-b[1]),
                        "text": norm(b[4])
                    })
    except Exception:
        pass
    return toks, "pymupdf"

def tokens_ocr(pdf_path):
    if not (convert_from_path and pytesseract): return [], "ocr"
    toks = []
    try:
        images = convert_from_path(pdf_path, dpi=OCR_DPI, poppler_path=POPPLER_PATH)
    except Exception:
        return [], "ocr"
    for pidx, img in enumerate(images):
        try:
            data = pytesseract.image_to_data(img, lang="spa+eng", output_type=pytesseract.Output.DICT,
                                             config="--psm 6 --oem 3")
        except Exception:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT,
                                             config="--psm 6 --oem 3")
        n = len(data["text"])
        for i in range(n):
            txt = norm(data["text"][i])
            if not txt: continue
            x = float(data["left"][i]); y = float(data["top"][i])
            w = float(data["width"][i]); h = float(data["height"][i])
            toks.append({"page": pidx, "x": x, "y": y, "w": w, "h": h, "text": txt})
    return toks, "ocr"

def get_tokens(pdf_path):
    toks, src = tokens_pdfplumber(pdf_path)
    if len(toks) < MIN_TOKENS_THRESHOLD:
        toks2, src2 = tokens_pymupdf(pdf_path)
        if len(toks2) > len(toks): toks, src = toks2, src2
    if len(toks) < MIN_TOKENS_THRESHOLD:
        toks3, src3 = tokens_ocr(pdf_path)
        if len(toks3) > len(toks): toks, src = toks3, src3
    return toks, src

# === Agrupación por filas y columnas ===
def group_lines(tokens, y_tol=5.0):
    lines = []
    tokens_sorted = sorted(tokens, key=lambda t: (t["page"], t["y"], t["x"]))
    current = []; cur_page = None; cur_y = None
    for t in tokens_sorted:
        if cur_page is None:
            cur_page, cur_y = t["page"], t["y"]
            current = [t]; continue
        if t["page"] != cur_page or abs(t["y"] - cur_y) > y_tol:
            lines.append((cur_page, cur_y, sorted(current, key=lambda z: z["x"])))
            cur_page, cur_y, current = t["page"], t["y"], [t]
        else:
            cur_y = (cur_y + t["y"]) / 2
            current.append(t)
    if current:
        lines.append((cur_page, cur_y, sorted(current, key=lambda z: z["x"])))
    return lines

def detect_columns(all_lines):
    xs = []
    for _, _, toks in all_lines:
        for i in range(1, len(toks)):
            gap = toks[i]["x"] - (toks[i-1]["x"] + toks[i-1]["w"])
            if gap > 12: xs.append(toks[i]["x"])
    if not xs: return []
    xs_sorted = sorted(xs)
    cols = [xs_sorted[0]]
    for x in xs_sorted[1:]:
        if abs(x - cols[-1]) > 25:
            cols.append(x)
    return cols

def tokens_to_fields(toks_line):
    if not toks_line: 
        return None

    toks_line = join_time_tokens(toks_line)
    texts = [t["text"] for t in toks_line if t["text"]]

    nums = [i for i, s in enumerate(texts) if re.fullmatch(r"\d+", s)]
    if len(nums) < 2:
        return None
    i_pos, i_num = nums[0], nums[1]

    time_idx = [i for i, s in enumerate(texts) if is_time_token(s)]
    if not time_idx:
        return None
    i_rec_time = time_idx[0]
    i_tf = time_idx[1] if len(time_idx) > 1 else time_idx[0]

    i_laps = None
    for i in range(len(texts) - 1, -1, -1):
        if re.fullmatch(r"\d+", texts[i]) and i > i_tf:
            i_laps = i
            break
    if i_laps is None:
        return None

    rec_secs = None
    penalty_count = None
    note = None

    mid_tokens = texts[i_tf + 1:i_laps]
    for tok in mid_tokens:
        if tok == ".":
            rec_secs = 0.0
        elif re.fullmatch(r"N/L|-", tok, flags=re.IGNORECASE):
            rec_secs = 0.0 if rec_secs is None else rec_secs
        elif re.fullmatch(r"\d+[.,]?\d*", tok):
            val = float(tok.replace(",", "."))
            if "." in tok or val <= 10:
                if rec_secs is None:
                    rec_secs = val
            else:
                penalty_count = int(val)

    if rec_secs is None:
        rec_secs = 0.0

    if (i_laps + 1) < len(texts):
        note = norm(" ".join(texts[i_laps + 1:])) or None

    name = norm(" ".join(texts[i_num + 1:i_rec_time]))

    rec_time_str = clean_time_str(texts[i_rec_time])
    t_final = clean_time_str(texts[i_tf])

    try:
        return {
            "position": int(texts[i_pos]),
            "number": int(texts[i_num]),
            "name": name,
            "rec": round(rec_secs, 3),                    # recargo en segundos
            "rec_str": None if rec_time_str is None else rec_time_str.replace(",", "."),
            "t_final": None if t_final is None else t_final.replace(",", "."),
            "laps": int(texts[i_laps]),
            "penalty": penalty_count,
            "penalty_note": note
        }
    except Exception:
        return None

# === Parse completo por archivo ===
def parse_tokens_to_results(tokens):
    if not tokens: return []

    lines = group_lines(tokens, y_tol=6.0)

    start_idx = 0
    for i, (_, _, toks) in enumerate(lines):
        low = " ".join(t["text"].lower() for t in toks)
        if "pos" in low and "nom" in low:
            start_idx = i + 1
            break

    results = []
    for _, _, toks in lines[start_idx:]:
        if len(toks) < 4: 
            continue
        row = tokens_to_fields(toks)
        if row:
            results.append(row)

    return results

def extract_meta(tokens):
    fecha = None; hora = None
    for t in tokens[:200]:
        s = t["text"]
        m_f = re.search(r"(?:Fecha|FECHA)\s*[: ]\s*(\d{1,2}/\d{1,2}/\d{4})", s)
        if m_f: fecha = m_f.group(1)
        m_h = re.search(r"(?:Hora|HORA)\s*[: ]\s*(\d{1,2}:\d{2})", s)
        if m_h: hora = m_h.group(1)
    return fecha, hora

def detect_race_type(filename):
    low = filename.lower()
    def num_after(word):
        m = re.search(fr"{word}\s*(\d+)", filename, re.IGNORECASE)
        return m.group(1) if m else None
    for key in ("serie", "repechaje", "semifinal", "prefinal", "final"):
        if key in low:
            n = num_after(key)
            if key == "final" and "prefinal" in low:
                continue
            return f"{key}{n}" if n else key
    return "unknown"

def process_pdf(pdf_path):
    tokens, extractor = get_tokens(pdf_path)
    fecha, hora = extract_meta(tokens)
    results = parse_tokens_to_results(tokens)

    dbg = Path(pdf_path).name + ".debug.json"
    with open(os.path.join(DEBUG_DIR, dbg), "w", encoding="utf-8") as f:
        json.dump({
            "extractor": extractor,
            "tokens": len(tokens),
            "parsed_rows": len(results)
        }, f, ensure_ascii=False, indent=2)

    if not results:
        print(f"Omitiendo {Path(pdf_path).name}: sin datos (extractor={extractor}, tokens={len(tokens)})")
        return None

    return {"date": fecha, "time": hora, "results": results}

# === Reconstrucción/limpieza total de manifiestos según el disco ===
def rebuild_manifests_from_disk():
    print("[SYNC] Reconstruyendo manifiestos desde resultados/ ...")
    fechas_validas = []

    # Buscar subcarpetas tipo 'Fecha NN'
    for nombre in os.listdir(OUTPUT_DIR):
        fecha_dir = os.path.join(OUTPUT_DIR, nombre)
        if not (os.path.isdir(fecha_dir) and re.match(r"^Fecha\s*\d+$", nombre, re.IGNORECASE)):
            continue

        # carreras presentes (por archivo existente)
        races = []
        for fn in os.listdir(fecha_dir):
            if not fn.lower().endswith(".json"):
                continue
            if fn.lower() == "index.json":
                continue
            base = os.path.splitext(fn)[0].lower()
            # aceptar nombres válidos
            if re.match(r"^(serie\d+|repechaje\d+|semifinal\d+|prefinal|final)$", base):
                races.append(base)

        races = sorted(set(races), key=race_sort_key)

        index_path = os.path.join(fecha_dir, "index.json")
        if races:
            save_json(index_path, {"races": races})
            fechas_validas.append(nombre)
        else:
            # si no tiene carreras, eliminar index vacío (si existiera)
            if os.path.exists(index_path):
                try:
                    os.remove(index_path)
                except Exception:
                    pass

    # escribir fechas.json solo con fechas que tengan al menos 1 carrera
    fechas_validas.sort(key=lambda s: int(re.search(r"\d+", s).group()))
    save_json(os.path.join(OUTPUT_DIR, "fechas.json"), {"fechas": fechas_validas})
    print(f"[SYNC] fechas.json actualizado. Fechas: {fechas_validas}")

def process_pdfs():
    if not os.path.exists(PDF_DIR):
        print(f"Error: No existe {PDF_DIR}")
        return

    for fecha_dir in os.listdir(PDF_DIR):
        fecha_path = os.path.join(PDF_DIR, fecha_dir)
        if not (os.path.isdir(fecha_path) and fecha_dir.lower().startswith("fecha")):
            continue

        pdf_files = [f for f in os.listdir(fecha_path) if f.lower().endswith(".pdf")]
        if not pdf_files:
            continue

        out_dir = os.path.join(OUTPUT_DIR, fecha_dir)
        os.makedirs(out_dir, exist_ok=True)

        for pdf_file in sorted(pdf_files):
            pdf_path = os.path.join(fecha_path, pdf_file)
            data = process_pdf(pdf_path)
            if not data:
                # preview de texto rápido por si querés inspeccionar
                txt_out = os.path.join(DEBUG_DIR, pdf_file + ".txt")
                try:
                    tokens, _ = get_tokens(pdf_path)
                    lines = group_lines(tokens)
                    with open(txt_out, "w", encoding="utf-8") as f:
                        f.write("[preview]\n")
                        for _, _, toks in lines[:80]:
                            f.write(" ".join(t["text"] for t in toks) + "\n")
                except Exception:
                    pass
                continue

            race_type = detect_race_type(pdf_file)
            out_path = os.path.join(out_dir, f"{race_type}.json")
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"JSON guardado: {out_path}")

            update_manifests(fecha_dir, race_type)

if __name__ == "__main__":
    # 1) Procesar PDFs y actualizar manifest de forma incremental
    process_pdfs()
    # 2) Reconstruir/limpiar manifiestos para reflejar deletions/moves
    rebuild_manifests_from_disk()
    # 3) Intentar subir si tenés el helper local
    try:
        import subir_jsons
        subir_jsons.subir_jsons()
    except Exception as e:
        print(f"Aviso: no pude ejecutar subir_jsons aquí ({e}).")
