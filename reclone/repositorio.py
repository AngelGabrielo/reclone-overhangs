"""Acceso a la base de datos: consultas y operaciones de escritura."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import pandas as pd
import psycopg
from psycopg.rows import dict_row

from . import adn, combinaciones as comb, config


class ErrorValidacion(Exception):
    """Un dato fue rechazado por una regla del dominio."""


# Mensajes legibles para las restricciones con nombre de db/esquema.sql.
_MENSAJES = {
    "parte_overhangs_segun_sintaxis": "los overhangs no corresponden al tipo de parte en esa sintaxis",
    "parte_secuencia_bases": "la secuencia solo puede contener A, C, G y T",
    "parte_sin_sitio_bsai": "la secuencia contiene un sitio BsaI interno (GGTCTC/GAGACC)",
    "parte_nombre_unico": "ya existe una parte con ese nombre",
    "parte_odc_unico": "ya existe una parte con ese ID de ODC",
    "plasmido_codigo_unico": "ya existe un plásmido con ese código",
    "constructo_nombre_unico": "ya existe un constructo con ese nombre",
    "constructo_estado_valido": "estado no válido",
    "overhang_formato": "un overhang debe tener 4 bases A/C/G/T",
    "overhang_no_palindromico": "el overhang es palindrómico (se liga consigo mismo)",
    "constructo_parte_parte_id_fkey": "la parte está siendo usada en constructos",
    "plasmido_parte_id_fkey": "la parte tiene plásmidos asociados",
}


def mensaje_error(error: psycopg.Error) -> str:
    diag = getattr(error, "diag", None)
    restriccion = getattr(diag, "constraint_name", None)
    if restriccion in _MENSAJES:
        return _MENSAJES[restriccion]
    principal = getattr(diag, "message_primary", None)
    return principal or str(error).strip()


@contextmanager
def conectar(url: str | None = None) -> Iterator[psycopg.Connection]:
    """Conexión con transacción: COMMIT al salir bien, ROLLBACK si hay error."""
    try:
        conn = psycopg.connect(url or config.DATABASE_URL, row_factory=dict_row)
    except psycopg.OperationalError as e:
        raise ConnectionError(
            "No hay conexión con PostgreSQL. Inicia el servidor con "
            "'python -m reclone db iniciar'.\n" + str(e)) from e
    try:
        with conn:
            yield conn
    except psycopg.Error as e:
        raise ErrorValidacion(mensaje_error(e)) from e
    finally:
        conn.close()


def _df(conn: psycopg.Connection, consulta: str, params=None) -> pd.DataFrame:
    filas = conn.execute(consulta, params).fetchall()
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Esquema
# ---------------------------------------------------------------------------

def crear_esquema(reiniciar: bool = False, url: str | None = None) -> None:
    """Crea tablas, funciones, vistas y catálogo. Con reiniciar=True BORRA todo."""
    with conectar(url) as conn:
        existe = conn.execute("SELECT to_regclass('public.parte') AS t").fetchone()["t"]
        if existe and not reiniciar:
            raise ErrorValidacion("El esquema ya existe. Usa --reiniciar para borrarlo y recrearlo.")
        if reiniciar:
            conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        for archivo in ("esquema.sql", "catalogo.sql"):
            conn.execute((config.DIR_SQL / archivo).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Lecturas
# ---------------------------------------------------------------------------

def conteos() -> dict[str, int]:
    tablas = ["sintaxis", "tipo_parte", "regla_sintaxis", "parte", "plasmido",
              "vector_destino", "constructo", "constructo_parte"]
    with conectar() as conn:
        return {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in tablas}


def sintaxis() -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, "SELECT id, nombre, enzima, descripcion FROM sintaxis ORDER BY id")


def tipos_parte(sintaxis_nombre: str | None = None) -> pd.DataFrame:
    """Tipos de parte; con sintaxis, solo los de ella y ordenados por posición."""
    with conectar() as conn:
        return _df(conn, """
            SELECT tp.id, tp.nombre, r.orden, tp.funcion
            FROM tipo_parte tp
            JOIN regla_sintaxis r ON r.tipo_parte_id = tp.id
            JOIN sintaxis s       ON s.id = r.sintaxis_id
            WHERE %(s)s::text IS NULL OR s.nombre = %(s)s
            ORDER BY r.orden, tp.nombre""", {"s": sintaxis_nombre}).drop_duplicates("nombre")


def reglas(sintaxis_nombre: str | None = None) -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, """
            SELECT s.nombre AS sintaxis, tp.nombre AS tipo, r.orden,
                   r.overhang_izq, r.overhang_der
            FROM regla_sintaxis r
            JOIN sintaxis s    ON s.id = r.sintaxis_id
            JOIN tipo_parte tp ON tp.id = r.tipo_parte_id
            WHERE %(s)s::text IS NULL OR s.nombre = %(s)s
            ORDER BY s.id, r.orden, tp.nombre""", {"s": sintaxis_nombre})


def vectores() -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, """
            SELECT v.id, v.nombre, s.nombre AS sintaxis, v.overhang_inicio,
                   v.overhang_fin, v.resistencia
            FROM vector_destino v JOIN sintaxis s ON s.id = v.sintaxis_id
            ORDER BY v.id""")


def partes(sintaxis_nombre: str | None = None, tipo: str | None = None,
           texto: str | None = None) -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, """
            SELECT * FROM vista_parte
            WHERE (%(s)s::text IS NULL OR sintaxis = %(s)s)
              AND (%(t)s::text IS NULL OR tipo = %(t)s)
              AND (%(q)s::text IS NULL OR nombre ILIKE '%%' || %(q)s || '%%'
                                       OR descripcion ILIKE '%%' || %(q)s || '%%')
            ORDER BY sintaxis, orden, nombre""",
            {"s": sintaxis_nombre, "t": tipo, "q": texto or None})


def plasmidos() -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, """
            SELECT pl.id, pl.codigo, p.nombre AS parte, tp.nombre AS tipo,
                   pl.backbone, pl.resistencia, pl.ubicacion, pl.creado_en
            FROM plasmido pl
            JOIN parte p       ON p.id = pl.parte_id
            JOIN tipo_parte tp ON tp.id = p.tipo_parte_id
            ORDER BY pl.codigo""")


def constructos() -> pd.DataFrame:
    with conectar() as conn:
        return _df(conn, "SELECT * FROM vista_constructo ORDER BY creado_en DESC, id DESC")


def detalle_constructo(nombre: str) -> tuple[dict, list[adn.PiezaEnsamblaje]]:
    with conectar() as conn:
        cabecera = conn.execute("""
            SELECT c.id, c.nombre, c.estado, c.notas, v.nombre AS vector,
                   v.overhang_inicio, v.overhang_fin, v.resistencia
            FROM constructo c JOIN vector_destino v ON v.id = c.vector_id
            WHERE c.nombre = %s""", (nombre,)).fetchone()
        if not cabecera:
            raise ErrorValidacion(f"No existe el constructo '{nombre}'")
        filas = conn.execute("""
            SELECT p.nombre, p.overhang_izq, p.secuencia, p.overhang_der, tp.nombre AS tipo
            FROM constructo_parte cp
            JOIN parte p       ON p.id = cp.parte_id
            JOIN tipo_parte tp ON tp.id = p.tipo_parte_id
            WHERE cp.constructo_id = %s ORDER BY cp.posicion""", (cabecera["id"],)).fetchall()
    return cabecera, [adn.PiezaEnsamblaje(**f) for f in filas]


# ---------------------------------------------------------------------------
# Combinaciones
# ---------------------------------------------------------------------------

def _grafo_del_vector(conn, vector_id: int):
    v = conn.execute("SELECT * FROM vector_destino WHERE id = %s", (vector_id,)).fetchone()
    filas = conn.execute("""
        SELECT p.nombre, p.overhang_izq AS izq, p.overhang_der AS der, r.orden
        FROM parte p
        JOIN regla_sintaxis r ON r.sintaxis_id = p.sintaxis_id AND r.tipo_parte_id = p.tipo_parte_id
        WHERE p.sintaxis_id = %s""", (v["sintaxis_id"],)).fetchall()
    return v, [comb.ParteGrafo(f["nombre"], f["izq"], f["der"], f["orden"]) for f in filas]


def espacio_combinaciones(vector_id: int, incluir: list[str] | None = None) -> comb.Constructos:
    """Espacio de constructos válidos del vector, con conteo exacto y acceso por número."""
    with conectar() as conn:
        v, grafo = _grafo_del_vector(conn, vector_id)
    return comb.Constructos(grafo, v["overhang_inicio"], v["overhang_fin"], incluir or [])


def a_tabla(caminos: list[list[str]], numeros: list[int] | None = None) -> pd.DataFrame:
    """Lista de caminos -> tabla con una columna por posición (largo variable)."""
    largo = max((len(c) for c in caminos), default=0)
    filas = [c + [None] * (largo - len(c)) for c in caminos]
    df = pd.DataFrame(filas, columns=[f"Pos. {i + 1}" for i in range(largo)])
    if numeros is not None:
        df.insert(0, "N.º", numeros)
    return df


def combinaciones(vector_id: int, incluir: list[str] | None = None,
                  limite: int = 500, desplazamiento: int = 0) -> pd.DataFrame:
    """Constructos válidos (aún no guardados) que se pueden armar con las partes existentes."""
    espacio = espacio_combinaciones(vector_id, incluir)
    return a_tabla(espacio.pagina(desplazamiento, limite))


def total_combinaciones(vector_id: int, incluir: list[str] | None = None) -> int:
    """Total de combinaciones posibles (con el filtro), calculado sin enumerarlas."""
    return espacio_combinaciones(vector_id, incluir).total


# ---------------------------------------------------------------------------
# Escrituras
# ---------------------------------------------------------------------------

def crear_parte(nombre: str, tipo: str, sintaxis_nombre: str,
                secuencia: str | None = None, descripcion: str | None = None,
                overhang_izq: str | None = None, overhang_der: str | None = None) -> int:
    """Crea una parte. Si no se dan overhangs, se toman de la regla de la sintaxis."""
    with conectar() as conn:
        return _insertar_parte(conn, nombre, tipo, sintaxis_nombre, secuencia,
                               descripcion, overhang_izq, overhang_der)


def _insertar_parte(conn, nombre, tipo, sintaxis_nombre, secuencia, descripcion,
                    overhang_izq, overhang_der, odc_id=None, bbf_id=None, coleccion=None) -> int:
    regla = conn.execute("""
        SELECT r.sintaxis_id, r.tipo_parte_id, r.overhang_izq, r.overhang_der
        FROM regla_sintaxis r
        JOIN sintaxis s    ON s.id = r.sintaxis_id
        JOIN tipo_parte tp ON tp.id = r.tipo_parte_id
        WHERE s.nombre = %s AND tp.nombre = %s""", (sintaxis_nombre, tipo)).fetchone()
    if not regla:
        raise ErrorValidacion(f"no hay regla para el tipo '{tipo}' en la sintaxis '{sintaxis_nombre}'")
    fila = conn.execute("""
        INSERT INTO parte (nombre, sintaxis_id, tipo_parte_id, overhang_izq, overhang_der,
                           secuencia, descripcion, odc_id, bbf_id, coleccion)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""", (
        nombre, regla["sintaxis_id"], regla["tipo_parte_id"],
        overhang_izq or regla["overhang_izq"], overhang_der or regla["overhang_der"],
        adn.normalizar(secuencia) or None, descripcion or None,
        odc_id or None, bbf_id or None, coleccion or None)).fetchone()
    return fila["id"]


def eliminar_parte(nombre: str) -> None:
    with conectar() as conn:
        if conn.execute("DELETE FROM parte WHERE nombre = %s", (nombre,)).rowcount == 0:
            raise ErrorValidacion(f"No existe la parte '{nombre}'")


def crear_plasmido(codigo: str, parte_nombre: str, resistencia: str,
                   backbone: str = "pOpen_v3", ubicacion: str | None = None) -> int:
    with conectar() as conn:
        parte = conn.execute("SELECT id FROM parte WHERE nombre = %s", (parte_nombre,)).fetchone()
        if not parte:
            raise ErrorValidacion(f"No existe la parte '{parte_nombre}'")
        return conn.execute("""
            INSERT INTO plasmido (codigo, parte_id, backbone, resistencia, ubicacion)
            VALUES (%s, %s, %s, %s, %s) RETURNING id""",
            (codigo, parte["id"], backbone, resistencia, ubicacion or None)).fetchone()["id"]


def nombre_sugerido(prefijo: str = "CON") -> str:
    """Siguiente código libre y corto para un constructo: CON-0001, CON-0002, ..."""
    with conectar() as conn:
        fila = conn.execute(r"""
            SELECT COALESCE(max(substring(nombre FROM '^' || %(p)s || '-(\d+)$')::int), 0) + 1 AS n
            FROM constructo WHERE nombre ~ ('^' || %(p)s || '-\d+$')""", {"p": prefijo}).fetchone()
    return f"{prefijo}-{fila['n']:04d}"


def crear_constructo(nombre: str, vector_nombre: str, partes_nombres: list[str],
                     notas: str | None = None) -> int:
    """Crea el constructo y sus partes en UNA transacción; el trigger valida al COMMIT."""
    if not nombre or not nombre.strip():
        raise ErrorValidacion("el constructo necesita un nombre")
    with conectar() as conn:
        vector = conn.execute("SELECT id FROM vector_destino WHERE nombre = %s",
                              (vector_nombre,)).fetchone()
        if not vector:
            raise ErrorValidacion(f"No existe el vector '{vector_nombre}'")
        ids = {r["nombre"]: r["id"] for r in conn.execute(
            "SELECT id, nombre FROM parte WHERE nombre = ANY(%s)", (partes_nombres,)).fetchall()}
        faltan = [p for p in partes_nombres if p not in ids]
        if faltan:
            raise ErrorValidacion("No existen las partes: " + ", ".join(faltan))
        constructo_id = conn.execute(
            "INSERT INTO constructo (nombre, vector_id, notas) VALUES (%s, %s, %s) RETURNING id",
            (nombre, vector["id"], notas or None)).fetchone()["id"]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO constructo_parte (constructo_id, posicion, parte_id) VALUES (%s, %s, %s)",
                [(constructo_id, i, ids[p]) for i, p in enumerate(partes_nombres, start=1)])
        return constructo_id


def actualizar_estado(nombre: str, estado: str, notas: str | None = None) -> None:
    with conectar() as conn:
        n = conn.execute("UPDATE constructo SET estado = %s, notas = COALESCE(%s, notas) "
                         "WHERE nombre = %s", (estado, notas, nombre)).rowcount
        if n == 0:
            raise ErrorValidacion(f"No existe el constructo '{nombre}'")


def eliminar_constructo(nombre: str) -> None:
    with conectar() as conn:
        if conn.execute("DELETE FROM constructo WHERE nombre = %s", (nombre,)).rowcount == 0:
            raise ErrorValidacion(f"No existe el constructo '{nombre}'")
