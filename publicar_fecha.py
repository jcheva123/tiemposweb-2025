"""Procesa los PDFs de una fecha y publica sus resultados en main."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import tempfile

REPO = Path(__file__).resolve().parent
RACE_KEY = re.compile(r"serie\d+|repechaje\d+|semifinal\d+|prefinal|final")


def git(*args, capture=False):
    return subprocess.run(
        ["git", *args], cwd=REPO, check=True, text=True, capture_output=capture
    ).stdout


def sincronizar():
    if git("branch", "--show-current", capture=True).strip() != "main":
        raise ValueError("Abrí la rama main para actualizar los resultados.")
    if git("status", "--porcelain", "--untracked-files=no", capture=True).strip():
        raise ValueError("Hay cambios pendientes en archivos de Git. Revisá git status.")
    git("pull", "--ff-only", "origin", "main")


def confirmar_en_github(date_path, mensaje):
    git("add", "--all", "--", "resultados/fechas.json", date_path.as_posix())
    if git("diff", "--cached", "--name-only", capture=True).strip():
        git("commit", "-m", mensaje)
    enviar_a_github()


def enviar_a_github():
    try:
        git("push", "origin", "HEAD:refs/heads/main")
    except subprocess.CalledProcessError as exc:
        raise ValueError(
            "GitHub no confirmó el envío. Volvé al menú y elegí 4 para reintentar."
        ) from exc


def pdfs_de(date_name):
    pdf_dir = REPO / "pdfs" / date_name
    return sorted(p for p in pdf_dir.glob("*") if p.is_file() and p.suffix.lower() == ".pdf")


def publicar(fecha):
    date_name = f"Fecha {fecha:02d}"
    pdfs = pdfs_de(date_name)
    if not pdfs:
        raise ValueError(f"No hay archivos PDF en {REPO / 'pdfs' / date_name}")
    sincronizar()

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

    confirmar_en_github(date_path, f"Actualizar resultados de {date_name}")
    print(f"Publicación en GitHub confirmada para {date_name}.")


def archivar_pdfs(pdfs, date_name):
    if not pdfs:
        return None
    archive_root = REPO.parent / "TIEMPOSWEB-PDF-retirados"
    archive_root.mkdir(exist_ok=True)
    archive = Path(tempfile.mkdtemp(prefix=f"{date_name} - ", dir=archive_root))
    moved = []
    try:
        for pdf in pdfs:
            pdf.rename(archive / pdf.name)
            moved.append(pdf)
    except OSError:
        for pdf in reversed(moved):
            (archive / pdf.name).rename(pdf)
        archive.rmdir()
        raise
    return archive


def retirar(fecha, fecha_entera):
    sincronizar()
    from process_pdfs import detect_race_type, race_sort_key, rebuild_manifests_from_disk

    date_name = f"Fecha {fecha:02d}"
    date_path = Path("resultados") / date_name
    races = {
        path.stem: path for path in date_path.glob("*.json")
        if path.is_file() and RACE_KEY.fullmatch(path.stem)
    }
    if not races:
        raise ValueError(f"{date_name} no tiene carreras publicadas en esta copia.")
    if fecha_entera:
        selected = list(races)
        count = len(selected)
        noun = "carrera" if count == 1 else "carreras"
        target = f"{date_name} completa ({count} {noun})"
    else:
        ordered = sorted(races, key=race_sort_key)
        for i, race in enumerate(ordered, start=1):
            label = re.sub(r"(\D)(\d)", r"\1 \2", race.upper(), count=1)
            print(f"  {i}. {label}")
        choice = int(input("Elegí el número de la carrera de la lista: "))
        if not 1 <= choice <= len(ordered):
            raise ValueError("Elegí un número de la lista.")
        selected = [ordered[choice - 1]]
        target = f"{date_name} / {selected[0]}"

    if input(f"Vas a retirar {target} de la web. Escribí RETIRAR para confirmar: ").strip().upper() != "RETIRAR":
        print("Operación cancelada.")
        return

    pdfs = [
        path for path in pdfs_de(date_name)
        if fecha_entera or detect_race_type(path.name) in selected
    ]
    archive = archivar_pdfs(pdfs, date_name)
    if archive:
        print(f"PDF guardado en: {archive}" if len(pdfs) == 1 else f"PDFs guardados en: {archive}")
    for race in selected:
        races[race].unlink()
    rebuild_manifests_from_disk()
    confirmar_en_github(date_path, f"Retirar {target}")
    print(f"Retiro en GitHub confirmado para {target}.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fecha", nargs="?", type=int)
    args = parser.parse_args()
    try:
        os.chdir(REPO)
        if args.fecha is None:
            print("1. Publicar o corregir resultados")
            print("2. Retirar una carrera")
            print("3. Retirar una fecha completa")
            print("4. Reintentar un envío pendiente")
            print("5. Publicar orden de partida")
            action = input("Elegí una opción (Enter para publicar): ").strip() or "1"
        else:
            action = "1"
        if action == "5":
            from publicar_series import main as publicar_orden

            publicar_orden()
            return
        if action == "4":
            sincronizar()
            enviar_a_github()
            print("Envío confirmado en GitHub.")
            return
        if action not in {"1", "2", "3"}:
            raise ValueError("Elegí una opción del 1 al 5.")
        fecha = args.fecha if args.fecha is not None else int(input("Número de la carpeta de fecha (01, 02, 03...): "))
        if not 1 <= fecha <= 99:
            raise ValueError("Ingresá un número de fecha entre 01 y 99.")
        if action == "1":
            publicar(fecha)
        else:
            retirar(fecha, fecha_entera=action == "3")
    except (ValueError, OSError, ImportError, subprocess.CalledProcessError, EOFError) as exc:
        parser.exit(1, f"No se completó la operación. {exc}\n")


if __name__ == "__main__":
    main()
