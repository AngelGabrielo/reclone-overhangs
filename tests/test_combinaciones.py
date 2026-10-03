from reclone.combinaciones import ParteGrafo as P, contar, enumerar

# Tabla del taller: 2 promotores, 2 RBS, 3 CDS, 2 terminadores
TALLER = ([P(f"P{i}", "GGAG", "TACT", 1) for i in (1, 2)]
          + [P(f"R{i}", "TACT", "CCAT", 2) for i in (1, 2)]
          + [P(n, "CCAT", "AGGT", 3) for n in ("GFP", "RFP", "LacZ")]
          + [P(f"T{i}", "AGGT", "CGCT", 4) for i in (1, 2)])

# Ciclo circular tipo levadura con una posición alternativa (puente que salta el oriT)
CICLO = [P("L", "ATGA", "GGAG", 1), P("pro", "GGAG", "AATG", 2), P("cds", "AATG", "GCTT", 3),
         P("term", "GCTT", "AGAC", 4), P("hr3", "AGAC", "CGAA", 5), P("puente", "AGAC", "GCAA", 5),
         P("oriT", "CGAA", "GCAA", 6), P("mark", "GCAA", "ATGA", 7)]


def test_conteo_taller():
    assert contar(TALLER, "GGAG", "CGCT") == 24


def test_enumeracion_coincide_con_conteo():
    todas = list(enumerar(TALLER, "GGAG", "CGCT"))
    assert len(todas) == 24 and len({tuple(t) for t in todas}) == 24


def test_incluir_filtra():
    con_gfp = list(enumerar(TALLER, "GGAG", "CGCT", ["GFP"]))
    assert len(con_gfp) == 8 and all("GFP" in c for c in con_gfp)
    assert len(list(enumerar(TALLER, "GGAG", "CGCT", ["GFP", "P1", "T2"]))) == 2
    assert list(enumerar(TALLER, "GGAG", "CGCT", ["GFP", "RFP"])) == []   # misma posición
    assert list(enumerar(TALLER, "GGAG", "CGCT", ["noexiste"])) == []


def test_ciclo_circular_con_alternativa():
    # camino largo (hr3 + oriT) y camino corto (puente)
    caminos = {tuple(c) for c in enumerar(CICLO, "ATGA", "ATGA")}
    assert caminos == {("L", "pro", "cds", "term", "hr3", "oriT", "mark"),
                       ("L", "pro", "cds", "term", "puente", "mark")}
    assert contar(CICLO, "ATGA", "ATGA") == 2
    assert [c for c in enumerar(CICLO, "ATGA", "ATGA", ["oriT"])] == [
        ["L", "pro", "cds", "term", "hr3", "oriT", "mark"]]
    # la última parte requerida cierra el camino sin tramo final
    assert len(list(enumerar(CICLO, "ATGA", "ATGA", ["mark"]))) == 2


def test_no_devuelve_constructos_vacios():
    assert list(enumerar([], "ATGA", "ATGA")) == []


def _fuerza_bruta(partes, inicio, fin, incluir=()):
    """Referencia independiente: DFS exhaustivo (solo para grafos pequeños)."""
    res = []

    def dfs(overhang, orden, camino):
        if overhang == fin and camino and set(incluir) <= {p.nombre for p in camino}:
            res.append([p.nombre for p in camino])
        for p in partes:
            if p.izq == overhang and p.orden > orden:
                dfs(p.der, p.orden, camino + [p])

    dfs(inicio, 0, [])
    return res


def test_numero_k_coincide_con_fuerza_bruta():
    from reclone.combinaciones import Constructos
    for partes, ini, fin in [(TALLER, "GGAG", "CGCT"), (CICLO, "ATGA", "ATGA")]:
        esperado = _fuerza_bruta(partes, ini, fin)
        espacio = Constructos(partes, ini, fin)
        assert espacio.total == len(esperado)
        obtenido = [espacio.numero(k) for k in range(espacio.total)]
        assert sorted(obtenido) == sorted(esperado) and len({tuple(c) for c in obtenido}) == len(esperado)


def test_conteo_con_filtro_es_exacto():
    from reclone.combinaciones import Constructos
    for incluir in (["GFP"], ["P1", "T2"], ["GFP", "P1", "T2"], ["R2", "LacZ"]):
        esperado = _fuerza_bruta(TALLER, "GGAG", "CGCT", incluir)
        espacio = Constructos(TALLER, "GGAG", "CGCT", incluir)
        assert espacio.total == len(esperado) > 0
        assert sorted(espacio.pagina(0, 100)) == sorted(esperado)


def test_paginas_contiguas_y_fuera_de_rango():
    import pytest
    from reclone.combinaciones import Constructos
    espacio = Constructos(TALLER, "GGAG", "CGCT")
    todas = espacio.pagina(0, 24)
    assert espacio.pagina(0, 10) + espacio.pagina(10, 10) + espacio.pagina(20, 10) == todas
    assert espacio.pagina(30, 5) == []
    with pytest.raises(IndexError):
        espacio.numero(24)


def test_acceso_directo_en_espacio_enorme():
    """Billones de combinaciones: saltar a cualquier posición no recorre las anteriores."""
    from reclone.combinaciones import Constructos
    partes = []
    for orden in range(1, 13):                       # 12 posiciones x 8 alternativas
        for i in range(8):
            partes.append(P(f"p{orden}_{i}", f"O{orden - 1}", f"O{orden}", orden))
    espacio = Constructos(partes, "O0", "O12")
    assert espacio.total == 8 ** 12
    assert espacio.numero(0) == [f"p{o}_0" for o in range(1, 13)]
    assert espacio.numero(espacio.total - 1) == [f"p{o}_7" for o in range(1, 13)]
    assert espacio.numero(8 ** 12 // 2)[0] == "p1_4"
