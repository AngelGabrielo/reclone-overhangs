"""Servidor PostgreSQL propio del proyecto, guardado en la carpeta .pg/.

Usa los binarios de la instalación de PostgreSQL existente, pero con su propio
directorio de datos y puerto (5433 por defecto), así no toca el servicio de
PostgreSQL del sistema ni necesita su contraseña. Solo escucha en 127.0.0.1.
"""

from __future__ import annotations

import glob
import shutil
import subprocess
import sys
from pathlib import Path

import psycopg
from psycopg import sql

from . import config


def _bin(programa: str) -> str:
    if config.PG_BIN:
        return str(Path(config.PG_BIN) / programa)
    if encontrado := shutil.which(programa):
        return encontrado
    candidatos = sorted(glob.glob(r"C:\Program Files\PostgreSQL\*\bin"),
                        key=lambda p: int(Path(p).parent.name) if Path(p).parent.name.isdigit() else 0)
    if candidatos:
        return str(Path(candidatos[-1]) / programa)
    raise FileNotFoundError(
        f"No encontré '{programa}'. Instala PostgreSQL o define PG_BIN en el archivo .env")


def _ejecutar(*args: str, desligado: bool = False) -> int:
    # Sin capturar la salida: en Windows, postgres hereda los pipes y
    # subprocess se quedaría esperando a que se cierren.
    # desligado: el proceso vive en su propia consola oculta. Si no, postgres
    # comparte la ventana de quien lo arrancó y Windows lo mata de golpe (sin
    # apagado ordenado) cuando esa ventana se cierra o se pulsa Ctrl+C.
    banderas = 0
    if desligado and sys.platform == "win32":
        banderas = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    return subprocess.call(list(args), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=banderas)


def inicializado() -> bool:
    return (config.PG_DATOS / "PG_VERSION").exists()


def corriendo() -> bool:
    if not inicializado():
        return False
    return _ejecutar(_bin("pg_ctl"), "status", "-D", str(config.PG_DATOS)) == 0


def inicializar() -> None:
    """Crea el directorio de datos (una sola vez)."""
    if inicializado():
        return
    config.PG_DATOS.parent.mkdir(parents=True, exist_ok=True)
    codigo = _ejecutar(_bin("initdb"), "-D", str(config.PG_DATOS), "-U", config.PG_USUARIO,
                       "-A", "trust", "-E", "UTF8", "--locale=C")
    if codigo != 0:
        raise RuntimeError("initdb falló creando el directorio de datos en " + str(config.PG_DATOS))


def iniciar() -> None:
    inicializar()
    if corriendo():
        return
    config.PG_LOG.parent.mkdir(parents=True, exist_ok=True)
    opciones = f"-p {config.PG_PUERTO} -c listen_addresses=127.0.0.1"
    codigo = _ejecutar(_bin("pg_ctl"), "start", "-w", "-D", str(config.PG_DATOS),
                       "-l", str(config.PG_LOG), "-o", opciones, desligado=True)
    if codigo != 0:
        raise RuntimeError(f"No se pudo iniciar PostgreSQL; revisa {config.PG_LOG}")
    crear_base()


def detener() -> None:
    if corriendo():
        _ejecutar(_bin("pg_ctl"), "stop", "-w", "-m", "fast", "-D", str(config.PG_DATOS))


def crear_base(nombre: str | None = None) -> None:
    """Crea la base de datos si no existe."""
    nombre = nombre or config.PG_BASE
    url = f"postgresql://{config.PG_USUARIO}@127.0.0.1:{config.PG_PUERTO}/postgres"
    with psycopg.connect(url, autocommit=True) as conn:
        existe = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (nombre,)).fetchone()
        if not existe:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(nombre)))
