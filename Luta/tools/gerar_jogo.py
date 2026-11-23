"""Gera o jogo para mandar para os amigos: dist/FalidoDaLuta.zip, com a pasta FalidoDaLuta e o
FalidoDaLuta.exe dentro. Quem recebe só descompacta e abre o .exe (não precisa de Python).

    python tools/gerar_jogo.py      (ou dois cliques no gerar_jogo.bat)

Instala o PyInstaller na primeira vez. Lembrete: no online os dois precisam da mesma versão,
então depois de mudar o jogo gere e mande de novo.
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # pasta Luta
NAME = "FalidoDaLuta"
ICON = os.path.join("assets", "images", "Logo", "logo.png")
LEAVE_OUT = {os.path.join("assets", "images", "Sprites", "raw")}     # originais: o jogo não usa
SOURCE_DIRS = (".", "online")       # os .py vão também como dados: o jogo confere a versão por eles
EXTRAS = ("LEIA-ME.txt",)           # vão soltos ao lado do .exe


def data_args():
    """--add-data de cada pasta de assets (sem as deixadas de fora) e dos .py da luta."""
    args = []
    for folder, dirs, files in os.walk("assets"):
        dirs[:] = sorted(d for d in dirs if os.path.join(folder, d) not in LEAVE_OUT)
        # um padrão por extensão ("*.png"): "*" sozinho também levaria as subpastas (até as de fora)
        for ext in sorted({os.path.splitext(name)[1] for name in files}):
            args += ["--add-data", f"{os.path.abspath(folder)}{os.sep}*{ext}{os.pathsep}{folder}"]
    for folder in SOURCE_DIRS:
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                args += ["--add-data", f"{os.path.abspath(os.path.join(folder, name))}{os.pathsep}{folder}"]
    return args


def ensure_pyinstaller():
    if importlib.util.find_spec("PyInstaller") is None:
        print("Instalando o PyInstaller (só na primeira vez)...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "pyinstaller"])


def main():
    os.chdir(ROOT)
    ensure_pyinstaller()
    command = [sys.executable, "-m", "PyInstaller", os.path.abspath("main.py"),
               "--name", NAME, "--windowed", "--noconfirm", "--clean",
               "--distpath", "dist", "--workpath", "build", "--specpath", "build",
               "--exclude-module", "numpy", "--exclude-module", "tkinter"]
    if importlib.util.find_spec("PIL") is not None:   # o PyInstaller precisa do Pillow para usar .png
        command += ["--icon", os.path.abspath(ICON)]
    command += data_args()
    print("Gerando o jogo (leva uns minutos)...")
    subprocess.check_call(command)

    folder = os.path.join("dist", NAME)
    for extra in EXTRAS:
        shutil.copy(extra, folder)
    archive = os.path.join("dist", NAME + ".zip")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, _, files in os.walk(folder):
            for name in files:
                path = os.path.join(base, name)
                zf.write(path, os.path.relpath(path, "dist"))
    size = os.path.getsize(archive) / 1e6
    print(f"\nPronto: {os.path.abspath(archive)} ({size:.0f} MB)")
    print("Mande esse .zip; quem receber descompacta e abre FalidoDaLuta.exe.")


if __name__ == "__main__":
    main()
