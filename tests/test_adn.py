from reclone import adn


def test_complemento_inverso():
    assert adn.complemento_inverso("AATG") == "CATT"
    assert adn.complemento_inverso("GGTCTC") == "GAGACC"


def test_palindromicos():
    assert adn.es_palindromico("GATC")
    assert not adn.es_palindromico("GGAG")


def test_problemas_parte_detecta_bsai_y_bases():
    assert adn.problemas_parte("GGAG", "TTGACG", "TACT") == []
    assert any("BsaI" in p for p in adn.problemas_parte("GGAG", "AAGGTCTCAA", "TACT"))
    assert any("BsaI" in p for p in adn.problemas_parte("GGAG", "AAGAGACCAA", "TACT"))
    assert any("inválidas" in p for p in adn.problemas_parte("GGAG", "AAXT", "TACT"))
    assert any("palindrómico" in p for p in adn.problemas_parte("GATC", "AAAA", "TACT"))


def test_digestion_parte_a_del_taller():
    region = "CGGGTCTCATACTAAAGAGGAGAAAAATGTGAGACCCG"
    [f] = adn.digerir_bsai(region)
    assert f.hebra_superior == "TACTAAAGAGGAGAAAAATG"
    assert f.overhang_izq == "TACT"
    assert f.overhang_der == "AATG"
    assert f.overhang_der_inferior == "CATT"
    assert f.inserto == "AAAGAGGAGAAA"


def test_ensamblaje_parte_d_del_taller():
    piezas = [
        adn.PiezaEnsamblaje("Promotor", "GGAG", "TTGACGGCTAGCTCAGTCCTAGGCAGTGCTAGC", "TACT"),
        adn.PiezaEnsamblaje("RBS", "TACT", "AAAGAGGAGAAA", "AATG"),
        adn.PiezaEnsamblaje("CDS", "AATG", "GCTTTTCCGGATGCATTCCGCATTCCGTGAGGAATGCATTCCG", "GCTT"),
        adn.PiezaEnsamblaje("Terminador", "GCTT", "CCCGCCGAAAGGCGGGTTTTTT", "CGCT"),
    ]
    r = adn.ensamblar("GGAG", "CGCT", piezas)
    assert r.problemas == []
    assert r.secuencia.startswith("GGAGTTGACG") and r.secuencia.endswith("TTTTTTCGCT")
    assert [r.secuencia[a:b] for a, b in r.cicatrices] == ["GGAG", "TACT", "AATG", "GCTT", "CGCT"]
    assert adn.sitios_bsai(r.secuencia) == []


def test_ensamblaje_detecta_incompatibles():
    piezas = [adn.PiezaEnsamblaje("P1", "GGAG", "AAA", "TACT"),
              adn.PiezaEnsamblaje("GFP", "CCAT", "CCC", "AGGT")]
    r = adn.ensamblar("GGAG", "AGGT", piezas)
    assert any("no son compatibles" in p for p in r.problemas)


def test_resumen_suma_partes_y_cicatrices_lineal():
    piezas = [adn.PiezaEnsamblaje("P", "GGAG", "A" * 30, "TACT", "Promotor"),
              adn.PiezaEnsamblaje("R", "TACT", "C" * 12, "AATG", "RBS"),
              adn.PiezaEnsamblaje("T", "AATG", "G" * 20, "CGCT", "Terminador")]
    res = adn.resumir("GGAG", "CGCT", piezas)
    assert not res.circular and res.cicatrices_pb == 16            # 4 overhangs x 4 pb
    assert res.total_pb == 30 + 12 + 20 + 16
    assert [f["pb"] for f in res.filas] == [30, 12, 20]
    assert abs(sum(f["porcentaje"] for f in res.filas) + 100 * 16 / res.total_pb - 100) < 0.3
    # coincide con la secuencia realmente ensamblada
    assert len(adn.ensamblar("GGAG", "CGCT", piezas).secuencia) == res.total_pb


def test_resumen_circular_cuenta_el_overhang_compartido_una_vez():
    piezas = [adn.PiezaEnsamblaje("L", "ATGA", "A" * 10, "GGAG", "x"),
              adn.PiezaEnsamblaje("M", "GGAG", "C" * 10, "ATGA", "y")]
    res = adn.resumir("ATGA", "ATGA", piezas)
    assert res.circular and res.cicatrices_pb == 8                 # 3 overhangs - 1 repetido
    # la secuencia lineal mostrada repite ATGA en ambos extremos: 4 pb de más
    assert len(adn.ensamblar("ATGA", "ATGA", piezas).secuencia) == res.total_pb + 4


def test_resumen_sin_secuencias():
    piezas = [adn.PiezaEnsamblaje("P1", "GGAG", None, "TACT", "Promotor"),
              adn.PiezaEnsamblaje("R1", "TACT", "AAA", "CCAT", "RBS")]
    res = adn.resumir("GGAG", "CCAT", piezas)
    assert res.total_pb is None and res.filas[0]["pb"] is None and res.filas[0]["porcentaje"] is None
