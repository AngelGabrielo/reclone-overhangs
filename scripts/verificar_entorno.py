"""Comprueba los requisitos antes de instalar (solo usa la biblioteca estándar).

Lo ejecuta instalar.bat con el Python del sistema, antes de crear el entorno.
Termina con código 0 si todo está bien y 1 si falta algo.
"""

from __future__ import annotations

import glob
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def pg_bin_configurado() -> str:
    """PG_BIN del archivo .env, si existe."""
    env = RAIZ / ".env"
    if env.exists():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.strip().startswith("PG_BIN="):
                return linea.split("=", 1)[1].strip().strip('"')
    return os.getenv("PG_BIN", "")


def buscar_initdb() -> Path | None:
    configurado = pg_bin_configurado()
    if configurado:
        candidato = Path(configurado) / "initdb.exe"
        return candidato if candidato.exists() else None
    if encontrado := shutil.which("initdb"):
        return Path(encontrado)
    versiones = glob.glob(r"C:\Program Files\PostgreSQL\*\bin\initdb.exe")
    return Path(max(versiones)) if versiones else None


def es_administrador_elevado() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def main() -> int:
    # La consola de Windows puede no tener todos los caracteres: nunca fallar al imprimir.
    sys.stdout.reconfigure(errors="replace")
    problemas: list[str] = []

    v = sys.version_info
    print(f"[{'OK' if v >= (3, 10) else 'X '}] Python {v.major}.{v.minor}.{v.micro}")
    if v < (3, 10):
        problemas.append("Se necesita Python 3.10 o superior: https://www.python.org/downloads/ "
                         "(marca la casilla «Add python.exe to PATH» al instalar).")

    initdb = buscar_initdb()
    print(f"[{'OK' if initdb else 'X '}] PostgreSQL" + (f" ({initdb.parent})" if initdb else ""))
    if not initdb:
        problemas.append("No encontré PostgreSQL. Instálalo con el instalador de "
                         "https://www.postgresql.org/download/windows/ (sirven las opciones por "
                         "defecto). Si ya lo tienes en otra carpeta, copia .env.example como .env "
                         "y escribe en PG_BIN la ruta de su carpeta «bin».")

    if sys.platform == "win32" and es_administrador_elevado():
        print("[X ] La terminal está abierta como administrador")
        problemas.append("PostgreSQL no arranca desde una terminal de administrador. "
                         "Cierra esta ventana y abre una normal (doble clic en instalar.bat).")
    else:
        print("[OK] Permisos de usuario normales")

    if problemas:
        print("\nFalta lo siguiente:\n")
        for p in problemas:
            print(" -", p)
        return 1
    print("\nTodo listo para instalar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
