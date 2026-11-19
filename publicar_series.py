"""Publica el TXT del orden de partida en el repositorio de Show Midget."""
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parent
WEB_REPO = REPO.parent / "SHOWMIDGET-SERIES"
WEB_URL = "https://github.com/jcheva123/showmidget.git"
WEB_FILE = Path("series/Nuevo orden de partida.txt")
SERIES_URL = "https://showmidget.ar/series/"
HEADER = re.compile(r"SERIE\s+([0-9]+)(?:\s+(.+))?", re.IGNORECASE)
LEGACY_ROW = re.compile(r"([0-9]+)\s+([0-9]+)\s+(.+)")
ROW = re.compile(r"([0-9]+)\s+(.+)")


def git(repo, *args, capture=False):
    return subprocess.run(
        ["git", "-C", str(repo), *args], check=True, text=True, capture_output=capture
    ).stdout


def read_grid(path):
    contents = path.read_bytes()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        charset = "utf-16" if contents.startswith((b"\xff\xfe", b"\xfe\xff")) else "cp1252"
        text = contents.decode(charset)
    if "\x00" in text:
        raise ValueError("Guardá el archivo como TXT con codificación UTF-8.")
    return "\n".join(text.splitlines()).rstrip() + "\n"


def validate_grid(text):
    counts = {}
    numbers = set()
    current = None
    for line_number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line in ("", "-", "–"):
            continue
        header = HEADER.fullmatch(line)
        if header:
            current = int(header[1])
            if not 1 <= current <= 22 or current in counts:
                raise ValueError(f"Línea {line_number}: número de serie fuera de rango o repetido.")
            counts[current] = 0
            numbers.clear()
            line = header[2]
            if not line:
                continue

        legacy = None if header else LEGACY_ROW.fullmatch(line)
        driver = ROW.fullmatch(line)
        if current is None or driver is None:
            raise ValueError(f"Línea {line_number}: se esperaba SERIE N o número y nombre del piloto.")
        number = int(legacy[2] if legacy else driver[1])
        if number in numbers:
            raise ValueError(f"Línea {line_number}: el auto {number} está repetido en la Serie {current}.")
        numbers.add(number)
        counts[current] += 1

    if not counts or not all(counts.values()):
        raise ValueError("El TXT debe incluir al menos una serie y cada serie debe tener pilotos.")
    return counts


def publish(text):
    if not WEB_REPO.exists():
        git(REPO, "clone", "--depth", "1", "--branch", "main", WEB_URL, str(WEB_REPO))
    for options in ((), ("--push",)):
        origin = git(WEB_REPO, "remote", "get-url", *options, "origin", capture=True).strip()
        if origin != WEB_URL:
            raise ValueError(f"Revisá el repositorio de origen en {WEB_REPO}.")
    if git(WEB_REPO, "branch", "--show-current", capture=True).strip() != "main":
        raise ValueError(f"La copia de publicación en {WEB_REPO} debe estar en main.")
    git(WEB_REPO, "pull", "--ff-only", "origin", "main")
    if git(WEB_REPO, "status", "--porcelain", "--untracked-files=no", capture=True).strip():
        raise ValueError(f"Hay cambios pendientes en {WEB_REPO}.")

    target = WEB_REPO / WEB_FILE
    if read_grid(target) != text:
        for key in ("user.name", "user.email"):
            identity = git(REPO, "config", "--get", key, capture=True).strip()
            git(WEB_REPO, "config", "--local", key, identity)
        target.write_text(text, encoding="utf-8", newline="\n")
        git(WEB_REPO, "commit", "--only", "-m", "Actualizar orden de partida", "--", WEB_FILE.as_posix())

    # Si se cortó la conexión después del commit, seleccionar el mismo TXT vuelve a intentar el envío.
    try:
        git(WEB_REPO, "push", "origin", "HEAD:refs/heads/main")
    except subprocess.CalledProcessError as exc:
        raise ValueError("GitHub no confirmó el envío. Volvé a elegir el mismo TXT para reintentar.") from exc


def main():
    from tkinter import Tk, filedialog, messagebox
    from tkinter import TclError

    try:
        window = Tk()
    except TclError as exc:
        raise ValueError("Windows no pudo abrir el selector de TXT de Python.") from exc
    window.withdraw()
    try:
        filename = filedialog.askopenfilename(
            parent=window, title="Elegí el TXT del orden de partida", filetypes=[("Archivo TXT", "*.txt")]
        )
        if not filename:
            return
        path = Path(filename)
        text = read_grid(path)
        counts = validate_grid(text)
        summary = "\n".join(f"Serie {number}: {count} autos" for number, count in sorted(counts.items()))
        confirmed = messagebox.askyesno(
            "Publicar orden de partida",
            f"{path.name}\n{len(counts)} series · {sum(counts.values())} autos\n\n"
            f"{summary}\n\nEste TXT reemplazará el orden de partida en Show Midget. ¿Publicar?",
            parent=window,
        )
    finally:
        window.destroy()
    if confirmed:
        publish(text)
        print(f"Orden de partida publicado en GitHub. Verificá en {SERIES_URL}")
