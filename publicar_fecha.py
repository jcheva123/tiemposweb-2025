"""Procesa los PDFs de una fecha y publica sus resultados en main."""
import argparse
import os
from pathlib import Path
import re
import subprocess

REPO = Path(__file__).resolve().parent
RACE_KEY = re.compile(r"serie\d+|repechaje\d+|semifinal\d+|prefinal|final")


def git(*args, capture=False):
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, text=True, capture_output=capture
    ).stdout


def publicar(fecha):
    date_name = f"Fecha {fecha:02d}"
    pdf_dir = REPO / "pdfs" / date_name
    pdfs = sorted(p for p in pdf_dir.glob("*") if p.is_file() and p.suffix.lower() == ".pdf")
    if not pdfs:
        raise ValueError(f"No hay archivos PDF en {pdf_dir}")
    if git("branch", "--show-current", capture=True).strip() != "main":
        raise ValueError("Abrí la rama main para publicar los resultados.")
    if git("status", "--porcelain", "--untracked-files=no", capture=True).strip():
        raise ValueError("Hay cambios pendientes en archivos de Git. Revisá git status antes de publicar.")

    git("pull", "--ff-only", "origin", "main")

    from process_pdfs import detect_race_type, process_pdf, rebuild_manifests_from_disk, save_json

    races = {}
    for pdf in pdfs:
        race = detect_race_type(pdf.name)
        if not RACE_KEY.fullmatch(race):
            raise ValueError(f"Nombre de carrera no reconocido: {pdf.name}")
        if race in races:
            raise ValueError(f"Hay más de un PDF para {race} en {date_name}.")
        data = process_pdf(str(pdf))
        if not data:
            raise ValueError(f"No se pudieron extraer resultados de {pdf.name}. Revisá el PDF y volvé a intentar.")
        races[race] = data

    date_path = Path("resultados") / date_name
    for race, data in races.items():
        save_json(str(date_path / f"{race}.json"), data)
    rebuild_manifests_from_disk()

    scope = ["resultados/fechas.json", date_path.as_posix()]
    git("add", "--", *scope)
    if git("diff", "--cached", "--name-only", capture=True).strip():
        git("commit", "-m", f"Actualizar resultados de {date_name}")

    # Si la subida anterior falló después del commit, este push también la reintenta.
    git("push", "origin", "HEAD:refs/heads/main")
    print(f"Publicación en GitHub confirmada para {date_name}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fecha", nargs="?", type=int)
    args = parser.parse_args()
    try:
        fecha = args.fecha if args.fecha is not None else int(input("Número de la carpeta de fecha (01, 02, 03...): "))
        if not 1 <= fecha <= 99:
            raise ValueError("Ingresá un número de fecha entre 1 y 99.")
        os.chdir(REPO)
        publicar(fecha)
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError, EOFError) as exc:
        parser.exit(1, f"No se completó la publicación. {exc}\n")


if __name__ == "__main__":
    main()
