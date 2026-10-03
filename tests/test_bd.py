"""Pruebas contra PostgreSQL, en una base aparte ('reclone_test') para no tocar los datos."""

import psycopg
import pytest

from reclone import config, importador, repositorio, servidor_local
from reclone.repositorio import ErrorValidacion

URL_TEST = f"postgresql://{config.PG_USUARIO}@127.0.0.1:{config.PG_PUERTO}/reclone_test"


@pytest.fixture(autouse=True)
def base_de_prueba(monkeypatch):
    try:
        servidor_local.crear_base("reclone_test")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL local no está corriendo (python -m reclone db iniciar)")
    monkeypatch.setattr(config, "DATABASE_URL", URL_TEST)
    repositorio.crear_esquema(reiniciar=True)
    importador.importar_partes(importador.leer_archivo(config.DIR_DATOS / "partes_taller.csv"))


def test_importacion_y_combinaciones():
    vectores = repositorio.vectores().set_index("nombre")
    vid = int(vectores.loc["Vector destino taller", "id"])
    assert repositorio.total_combinaciones(vid) == 24
    assert len(repositorio.combinaciones(vid, ["GFP"])) == 8


def test_constructo_valido():
    repositorio.crear_constructo("GFP_v1", "Vector destino taller", ["P1", "R1", "GFP", "T1"])
    fila = repositorio.constructos().iloc[0]
    assert fila["ensamblaje"] == "GGAG | P1 → R1 → GFP → T1 | CGCT"


@pytest.mark.parametrize("partes, mensaje", [
    (["P1", "GFP", "R1", "T1"], "no son compatibles"),
    (["P1", "R1"], "no cierra con el fin del vector"),
    (["R1", "GFP", "T1"], "no encaja con el inicio"),
    (["P1", "R1", "CDS_GG", "T1"], "otra sintaxis"),
])
def test_constructos_invalidos_se_rechazan(partes, mensaje):
    with pytest.raises(ErrorValidacion, match=mensaje):
        repositorio.crear_constructo("malo", "Vector destino taller", partes)
    assert repositorio.constructos().empty  # no quedó nada a medias


def test_restricciones_de_parte():
    with pytest.raises(ErrorValidacion, match="BsaI"):
        repositorio.crear_parte("Pbsa", "Promotor", "Taller 1", secuencia="AAGGTCTCAA")
    with pytest.raises(ErrorValidacion, match="overhangs no corresponden"):
        repositorio.crear_parte("Pmal", "Promotor", "Taller 1",
                                overhang_izq="AGGT", overhang_der="CGCT")
    with pytest.raises(ErrorValidacion, match="ya existe"):
        repositorio.crear_parte("P1", "Promotor", "Taller 1")


def test_no_se_borra_parte_en_uso():
    repositorio.crear_constructo("GFP_v1", "Vector destino taller", ["P1", "R1", "GFP", "T1"])
    with pytest.raises(ErrorValidacion, match="usada en constructos"):
        repositorio.eliminar_parte("GFP")


def test_importacion_todo_o_nada():
    df = importador.leer_archivo(config.DIR_DATOS / "partes_con_errores.csv")
    r = importador.importar_partes(df)
    assert not r.ok and r.importadas == 0
    assert "P3" not in set(repositorio.partes()["nombre"])  # la fila válida tampoco se guardó
    r = importador.importar_partes(df, todo_o_nada=False)
    assert r.importadas == 1
    assert "P3" in set(repositorio.partes()["nombre"])


def test_nombre_sugerido_es_corto_y_secuencial():
    assert repositorio.nombre_sugerido() == "CON-0001"
    repositorio.crear_constructo("CON-0001", "Vector destino taller", ["P1", "R1", "GFP", "T1"])
    repositorio.crear_constructo("Mi diseño", "Vector destino taller", ["P2", "R1", "GFP", "T1"])
    assert repositorio.nombre_sugerido() == "CON-0002"          # ignora nombres personalizados
    repositorio.crear_constructo("CON-0007", "Vector destino taller", ["P1", "R2", "GFP", "T1"])
    assert repositorio.nombre_sugerido() == "CON-0008"          # sigue tras el mayor, sin repetir
    assert repositorio.nombre_sugerido("XYZ") == "XYZ-0001"


def test_constructo_sin_nombre_se_rechaza():
    with pytest.raises(ErrorValidacion, match="necesita un nombre"):
        repositorio.crear_constructo("  ", "Vector destino taller", ["P1", "R1", "GFP", "T1"])
