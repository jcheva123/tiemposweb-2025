import os
import subprocess

repo_dir = os.environ.get("TIEMPOS_REPO", "C:/SHOWMIDGET/TIEMPOSWEB")

def subir_jsons():
    try:
        os.chdir(repo_dir)

        pull_result = subprocess.run(["git", "pull", "origin", "main"], capture_output=True, text=True)
        if pull_result.returncode != 0:
            print(f"Error al sincronizar con GitHub: {pull_result.stderr}")
            return

        status = subprocess.run(["git", "status", "--porcelain", "resultados"], capture_output=True, text=True)
        if not status.stdout.strip():
            print("No hay cambios en 'resultados' para subir")
            return

        add_result = subprocess.run(["git", "add", "resultados"], capture_output=True, text=True)
        if add_result.returncode != 0:
            print(f"Error al añadir archivos: {add_result.stderr}")
            return

        commit_result = subprocess.run(
            ["git", "commit", "-m", "Actualizar resultados JSON"],
            capture_output=True,
            text=True
        )
        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout.lower():
            print(f"Error al hacer commit: {commit_result.stderr}")
            return

        push_result = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if push_result.returncode == 0:
            print("JSONs subidos exitosamente")
        else:
            print(f"Error al empujar a GitHub: {push_result.stderr}")

    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar git: {e}\nDetalles: {e.stderr}")
    except Exception as e:
        print(f"Error inesperado: {e}")
