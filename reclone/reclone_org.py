"""Importación de las Open DNA Collections de Reclone.

Fuente: https://github.com/Reclone-org/Open-DNA-Collections (los datos de
reclone.org remiten a ese repositorio). Se usan las placas (`*/Platemaps/*.csv`)
vigentes, las que traen la columna `ODC ID`.

Cada fila es un plásmido con su secuencia completa. Para cada uno se simula el
corte con BsaI, se toma el fragmento liberado (la parte), se leen sus overhangs
y con ellos se deduce el tipo según la sintaxis "Reclone". Lo que no se puede
clasificar no se fuerza: queda en el informe de omitidas con su motivo.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import psycopg

from . import adn, config
from .repositorio import _insertar_parte, conectar, mensaje_error

REPO = "Reclone-org/Open-DNA-Collections"
SINTAXIS = "Reclone"
DIR_LOCAL = config.DIR_DATOS / "reclone"
_UA = {"User-Agent": "reclone-overhangs"}


# ---------------------------------------------------------------------------
# Descarga
# ---------------------------------------------------------------------------

def _get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=_UA), timeout=60) as r:
        return r.read()


def descargar(destino: Path = DIR_LOCAL, rama: str = "main", avisar=print) -> str:
    """Baja las placas, el índice de ODC y los README a `destino`. Devuelve el commit."""
    commit = json.loads(_get(f"https://api.github.com/repos/{REPO}/commits/{rama}"))["sha"]
    arbol = json.loads(_get(f"https://api.github.com/repos/{REPO}/git/trees/{commit}?recursive=1"))
    rutas = [x["path"] for x in arbol["tree"] if x["type"] == "blob" and (
        ("/Platemaps/" in x["path"] and x["path"].endswith(".csv"))
        or x["path"] == "odc_plasmids.csv"
        or (x["path"].endswith("README.md") and x["path"].count("/") == 1))]
    for i, ruta in enumerate(rutas, start=1):
        archivo = destino / ruta
        archivo.parent.mkdir(parents=True, exist_ok=True)
        archivo.write_bytes(_get(f"https://raw.githubusercontent.com/{REPO}/{commit}/"
                                 + urllib.parse.quote(ruta)))
        avisar(f"  [{i}/{len(rutas)}] {ruta}")
    (destino / "ORIGEN.txt").write_text(
        f"Repositorio: https://github.com/{REPO}\nCommit: {commit}\nArchivos: {len(rutas)}\n",
        encoding="utf-8")
    return commit


def commit_local(carpeta: Path = DIR_LOCAL) -> str | None:
    origen = carpeta / "ORIGEN.txt"
    if origen.exists():
        for linea in origen.read_text(encoding="utf-8").splitlines():
            if linea.startswith("Commit:"):
                return linea.split(":", 1)[1].strip()
    return None


# ---------------------------------------------------------------------------
# Lectura de placas
# ---------------------------------------------------------------------------

def leer_placas(carpeta: Path = DIR_LOCAL) -> pd.DataFrame:
    """Une las placas vigentes (con `ODC ID`) en una tabla normalizada."""
    archivos = sorted(carpeta.glob("*/Platemaps/*.csv"))
    if not archivos:
        raise FileNotFoundError(
            f"No hay placas en {carpeta}. Ejecuta con --descargar para bajarlas de GitHub.")
    trozos = []
    for archivo in archivos:
        df = pd.read_csv(archivo, dtype=str, keep_default_na=False)
        if "ODC ID" not in df.columns:
            continue  # versiones antiguas, con IDs que Reclone reemplazó por ODC
        nombre = df["Name"] if "Name" in df.columns else df.get("Gene or Insert Name", "")
        col = lambda c: df[c].str.strip() if c in df.columns else ""  # noqa: E731
        trozos.append(pd.DataFrame({
            "coleccion": archivo.parent.parent.name,
            "placa": archivo.stem,
            "pocillo": col("Well Location"),
            "odc_id": col("ODC ID"),
            "bbf_id": col("BBF ID"),
            "nombre": nombre.str.strip() if hasattr(nombre, "str") else "",
            "backbone": col("Backbone Name"),
            "resistencia": col("Bacterial Resistance"),
            "secuencia_plasmido": col("Construct Sequence"),
        }))
    df = pd.concat(trozos, ignore_index=True)
    df = df[(df["odc_id"] != "") | (df["nombre"] != "")]       # filas vacías de la placa
    return df.drop_duplicates(subset=["odc_id"], keep="first").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Importación
# ---------------------------------------------------------------------------

@dataclass
class ResultadoReclone:
    leidas: int = 0
    importadas: int = 0
    existentes: int = 0
    omitidas: list[dict] = field(default_factory=list)
    por_tipo: Counter = field(default_factory=Counter)
    commit: str | None = None

    def omitidas_df(self) -> pd.DataFrame:
        return pd.DataFrame(self.omitidas, columns=[
            "coleccion", "placa", "pocillo", "odc_id", "nombre", "motivo"])

    def motivos(self) -> Counter:
        return Counter(o["motivo"].split(":")[0] for o in self.omitidas)


def analizar_secuencia(secuencia_plasmido: str):
    """Devuelve (fragmento, None) o (None, motivo de omisión)."""
    s = adn.normalizar(secuencia_plasmido)
    if len(s) < 100:
        return None, "sin secuencia del plásmido"
    if not adn.es_secuencia_valida(s):
        raros = "".join(sorted(set(s) - set("ACGT")))
        return None, f"secuencia con bases no estándar: {raros}"
    fragmentos = adn.digerir_bsai(s)  # lineal: sitios BsaI apuntando hacia adentro
    if not fragmentos:
        return None, "sin fragmento BsaI (vector destino o sitios hacia afuera)"
    return min(fragmentos, key=lambda f: len(f.hebra_superior)), None


def importar(carpeta: Path = DIR_LOCAL) -> ResultadoReclone:
    """Importa las placas locales. Es idempotente: lo ya importado (por ODC ID) se salta."""
    placas = leer_placas(carpeta)
    res = ResultadoReclone(leidas=len(placas), commit=commit_local(carpeta))

    def omitir(fila, motivo):
        res.omitidas.append({k: fila[k] for k in
                             ("coleccion", "placa", "pocillo", "odc_id", "nombre")} | {"motivo": motivo})

    with conectar() as conn:
        tipo_por_par = {(r["overhang_izq"], r["overhang_der"]): r["tipo"] for r in conn.execute("""
            SELECT r.overhang_izq, r.overhang_der, tp.nombre AS tipo
            FROM regla_sintaxis r JOIN sintaxis s ON s.id = r.sintaxis_id
            JOIN tipo_parte tp ON tp.id = r.tipo_parte_id
            WHERE s.nombre = %s""", (SINTAXIS,)).fetchall()}
        if not tipo_por_par:
            raise RuntimeError(f"La sintaxis '{SINTAXIS}' no existe: ejecuta "
                               "'python -m reclone esquema --reiniciar'")
        odc_existentes = {r["odc_id"] for r in conn.execute(
            "SELECT odc_id FROM parte WHERE odc_id IS NOT NULL").fetchall()}
        nombres = {r["nombre"] for r in conn.execute("SELECT nombre FROM parte").fetchall()}
        codigos = {r["codigo"] for r in conn.execute("SELECT codigo FROM plasmido").fetchall()}

        for fila in placas.to_dict("records"):
            odc = fila["odc_id"]
            if not odc:
                omitir(fila, "sin ODC ID")
                continue
            if odc in odc_existentes:
                res.existentes += 1
                continue
            frag, motivo = analizar_secuencia(fila["secuencia_plasmido"])
            if frag is None:
                omitir(fila, motivo)
                continue
            par = (frag.overhang_izq, frag.overhang_der)
            tipo = tipo_por_par.get(par)
            if tipo is None:
                omitir(fila, f"overhangs fuera de la sintaxis: {par[0]}→{par[1]}")
                continue
            problemas = adn.problemas_parte(par[0], frag.inserto, par[1])
            if problemas:
                omitir(fila, "parte inválida: " + "; ".join(problemas))
                continue

            nombre = fila["nombre"] or odc
            if nombre in nombres:
                nombre = f"{nombre} ({odc})"
            try:
                with conn.transaction():  # savepoint: una fila mala no tumba las demás
                    _insertar_parte(
                        conn, nombre, tipo, SINTAXIS, frag.inserto,
                        f"{fila['coleccion']} · {fila['placa']}", par[0], par[1],
                        odc_id=odc, bbf_id=fila["bbf_id"], coleccion=fila["coleccion"])
                    codigo = odc if odc not in codigos else f"{odc}-{fila['placa']}"
                    conn.execute("""
                        INSERT INTO plasmido (codigo, parte_id, backbone, resistencia, ubicacion)
                        SELECT %s, id, %s, %s, %s FROM parte WHERE odc_id = %s""", (
                        codigo, fila["backbone"] or "No indicado",
                        fila["resistencia"] or "No indicada",
                        f"{fila['placa']} · {fila['pocillo']}", odc))
                nombres.add(nombre)
                codigos.add(codigo)
                odc_existentes.add(odc)
                res.importadas += 1
                res.por_tipo[(fila["coleccion"], tipo)] += 1
            except psycopg.Error as e:
                omitir(fila, f"la base de datos lo rechazó: {mensaje_error(e)}")
    return res
