"""Importación de partes desde CSV o Excel con reporte de errores por fila.

Modo por defecto "todo o nada": si alguna fila tiene errores no se guarda
ninguna, para que la base de datos nunca quede con una carga a medias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

import pandas as pd
import psycopg

from . import adn
from .repositorio import ErrorValidacion, _insertar_parte, conectar, mensaje_error

COLUMNAS_OBLIGATORIAS = ["nombre", "tipo", "sintaxis"]
COLUMNAS_OPCIONALES = ["overhang_izq", "overhang_der", "secuencia", "descripcion"]


@dataclass
class ResultadoImportacion:
    total: int = 0
    importadas: int = 0
    errores: list[dict] = field(default_factory=list)  # {"fila", "nombre", "error"}

    @property
    def ok(self) -> bool:
        return not self.errores

    def errores_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.errores, columns=["fila", "nombre", "error"])


def leer_archivo(origen: str | Path | BinaryIO, nombre_archivo: str | None = None) -> pd.DataFrame:
    """Lee CSV/XLSX como texto (sin que pandas 'adivine' tipos ni fechas)."""
    nombre = (nombre_archivo or str(origen)).lower()
    if nombre.endswith((".xlsx", ".xlsm", ".xls")):
        df = pd.read_excel(origen, dtype=str)
    else:
        df = pd.read_csv(origen, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [str(c).strip().lower() for c in df.columns]
    faltan = [c for c in COLUMNAS_OBLIGATORIAS if c not in df.columns]
    if faltan:
        raise ErrorValidacion("Faltan columnas obligatorias: " + ", ".join(faltan))
    for c in COLUMNAS_OPCIONALES:
        if c not in df.columns:
            df[c] = ""
    df = df[COLUMNAS_OBLIGATORIAS + COLUMNAS_OPCIONALES].fillna("")
    return df.apply(lambda col: col.astype(str).str.strip())


def importar_partes(df: pd.DataFrame, todo_o_nada: bool = True) -> ResultadoImportacion:
    resultado = ResultadoImportacion(total=len(df))
    vistos: set[str] = set()

    with conectar() as conn:
        reglas = {(r["sintaxis"], r["tipo"]): (r["overhang_izq"], r["overhang_der"])
                  for r in conn.execute("""
                      SELECT s.nombre AS sintaxis, tp.nombre AS tipo, r.overhang_izq, r.overhang_der
                      FROM regla_sintaxis r JOIN sintaxis s ON s.id = r.sintaxis_id
                      JOIN tipo_parte tp ON tp.id = r.tipo_parte_id""").fetchall()}
        sintaxis_ok = {s for s, _ in reglas}
        tipos_ok = {t for _, t in reglas}
        existentes = {r["nombre"] for r in conn.execute("SELECT nombre FROM parte").fetchall()}

        for i, fila in enumerate(df.to_dict("records"), start=2):  # fila 1 = cabecera
            nombre = fila["nombre"]
            secuencia = adn.normalizar(fila["secuencia"])
            izq = fila["overhang_izq"].upper()
            der = fila["overhang_der"].upper()
            problemas = []

            # 1) Validación previa con mensajes claros.
            if not nombre:
                problemas.append("falta el nombre")
            elif nombre in vistos:
                problemas.append("nombre repetido dentro del archivo")
            elif nombre in existentes:
                problemas.append("ya existe una parte con ese nombre en la base de datos")
            if fila["sintaxis"] not in sintaxis_ok:
                problemas.append(f"sintaxis '{fila['sintaxis']}' no existe")
            if fila["tipo"] not in tipos_ok:
                problemas.append(f"tipo de parte '{fila['tipo']}' no existe")
            regla = reglas.get((fila["sintaxis"], fila["tipo"]))
            if regla:
                izq, der = izq or regla[0], der or regla[1]
                if (izq, der) != regla:
                    problemas.append(f"overhangs {izq}-{der} no corresponden a un {fila['tipo']} "
                                     f"en '{fila['sintaxis']}' (debe ser {regla[0]}-{regla[1]})")
                else:
                    problemas += adn.problemas_parte(izq, secuencia, der)
            vistos.add(nombre)

            # 2) La base de datos tiene la última palabra (savepoint por fila).
            if not problemas:
                try:
                    with conn.transaction():
                        _insertar_parte(conn, nombre, fila["tipo"], fila["sintaxis"],
                                        secuencia, fila["descripcion"], izq, der)
                    resultado.importadas += 1
                except (psycopg.Error, ErrorValidacion) as e:
                    texto = mensaje_error(e) if isinstance(e, psycopg.Error) else str(e)
                    problemas.append(texto)

            for p in problemas:
                resultado.errores.append({"fila": i, "nombre": nombre, "error": p})

        if todo_o_nada and resultado.errores:
            conn.rollback()
            resultado.importadas = 0

    return resultado
