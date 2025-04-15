import os
import subprocess

# Directorio del repositorio
repo_dir = "C:/SHOWMIDGET/TIEMPOSWEB"

def subir_jsons():
    os.chdir(repo_dir)
    
    # Añadir archivos JSON
    subprocess.run(["git", "add", "resultados/*"])
    
    # Hacer commit
    result = subprocess.run(["git", "commit", "-m", "Actualizar resultados JSON"], capture_output=True, text=True)
    if result.returncode == 0:
        # Subir a GitHub
        subprocess.run(["git", "push", "origin", "main"])
        print("JSONs subidos exitosamente")
    else:
        print("No hay nuevos JSONs para subir")

if __name__ == "__main__":
    subir_jsons()