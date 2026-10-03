"""Configuración leída desde variables de entorno o el archivo .env."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

# Servidor PostgreSQL propio del proyecto (ver reclone/servidor_local.py).
PG_PUERTO = int(os.getenv("PG_PUERTO", "5433"))
PG_USUARIO = os.getenv("PG_USUARIO", "reclone")
PG_BASE = os.getenv("PG_BASE", "reclone")
PG_DATOS = Path(os.getenv("PG_DATOS", RAIZ / ".pg" / "datos"))
PG_LOG = Path(os.getenv("PG_LOG", RAIZ / ".pg" / "postgres.log"))
PG_BIN = os.getenv("PG_BIN", "")  # vacío = autodetectar

# Si se define, se usa este servidor en lugar del local (p. ej. uno compartido).
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{PG_USUARIO}@127.0.0.1:{PG_PUERTO}/{PG_BASE}",
)

DIR_SQL = RAIZ / "db"
DIR_DATOS = RAIZ / "datos"
