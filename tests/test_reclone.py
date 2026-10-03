"""Importación de Reclone (usa los datos locales de datos/reclone, sin red)."""

import psycopg
import pytest

from reclone import adn, config, reclone_org, repositorio, servidor_local

URL_TEST = f"postgresql://{config.PG_USUARIO}@127.0.0.1:{config.PG_PUERTO}/reclone_test"


def test_analizar_secuencia_casos():
    assert reclone_org.analizar_secuencia("ACGT")[1] == "sin secuencia del plásmido"
    assert "no estándar" in reclone_org.analizar_secuencia("ACGT" * 40 + "N")[1]
    assert "sin fragmento BsaI" in reclone_org.analizar_secuencia("ACGT" * 40)[1]
    parte = "AAAGGGGCCGTCAATATCAGGGTCTCTAATGATCCTGGATACTGATTATATCAC" + "ACGT" * 10 + \
            "AAGAGCTTTGAGACCACAGAACGAACAGGCACTACATCAAGGCATGGAACCCATC"
    frag, motivo = reclone_org.analizar_secuencia(parte)
    assert motivo is None and (frag.overhang_izq, frag.overhang_der) == ("AATG", "GCTT")


@pytest.fixture
def base_reclone(monkeypatch):
    if not (reclone_org.DIR_LOCAL / "ORIGEN.txt").exists():
        pytest.skip("faltan las placas de Reclone: ejecuta 'python -m reclone importar-reclone'")
    try:
        servidor_local.crear_base("reclone_test")
    except psycopg.OperationalError:
        pytest.skip("PostgreSQL local no está corriendo (python -m reclone db iniciar)")
    monkeypatch.setattr(config, "DATABASE_URL", URL_TEST)
    repositorio.crear_esquema(reiniciar=True)


def test_importacion_completa(base_reclone):
    r1 = reclone_org.importar()
    assert r1.importadas > 250
    assert r1.importadas + len(r1.omitidas) == r1.leidas
    assert set(r1.motivos()) <= {"sin fragmento BsaI (vector destino o sitios hacia afuera)",
                                 "sin secuencia del plásmido"}

    # es idempotente: una segunda pasada no duplica nada
    r2 = reclone_org.importar()
    assert r2.importadas == 0 and r2.existentes == r1.importadas

    partes = repositorio.partes("Reclone")
    assert len(partes) == r1.importadas
    assert partes["odc_id"].notna().all()
    assert len(repositorio.plasmidos()) == r1.importadas


def test_las_secuencias_importadas_son_validas(base_reclone):
    reclone_org.importar()
    for p in repositorio.partes("Reclone").itertuples():
        assert adn.problemas_parte(p.overhang_izq, p.secuencia or "", p.overhang_der) == []


@pytest.mark.parametrize("vector", ["Reclone E. coli", "Reclone levadura (circular)"])
def test_combinaciones_pasan_el_validador_de_la_base(base_reclone, vector):
    """Cada combinación generada en Python debe ser aceptada por el trigger de PostgreSQL."""
    reclone_org.importar()
    vid = int(repositorio.vectores().set_index("nombre").loc[vector, "id"])
    assert repositorio.total_combinaciones(vid) > 1000
    combos = repositorio.combinaciones(vid, limite=5)
    assert len(combos) == 5
    for i, fila in combos.iterrows():
        partes = [x for x in fila if isinstance(x, str)]
        repositorio.crear_constructo(f"prueba_{i}", vector, partes)
    assert len(repositorio.constructos()) == 5


def test_constructo_de_levadura_se_ensambla(base_reclone):
    reclone_org.importar()
    vid = int(repositorio.vectores().set_index("nombre").loc["Reclone levadura (circular)", "id"])
    partes = [x for x in repositorio.combinaciones(vid, ["Sc-pAdh1"], 1).iloc[0] if isinstance(x, str)]
    repositorio.crear_constructo("levadura_1", "Reclone levadura (circular)", partes)
    cab, piezas = repositorio.detalle_constructo("levadura_1")
    r = adn.ensamblar(cab["overhang_inicio"], cab["overhang_fin"], piezas)
    assert r.problemas == [] and r.secuencia
    assert r.secuencia.startswith("ATGA") and r.secuencia.endswith("ATGA")
    assert adn.sitios_bsai(r.secuencia) == []
