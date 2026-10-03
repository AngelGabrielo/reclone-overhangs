-- =====================================================================
-- Catálogo base: tipos de parte, sintaxis, reglas y vectores destino.
-- Las partes se cargan aparte (datos/*.csv o `python -m reclone importar-reclone`).
--
-- Cada regla = (sintaxis, tipo, orden, overhang izq., overhang der.).
-- El orden es el de la posición dentro de la sintaxis; tipos con el mismo
-- orden son alternativas entre sí.
-- =====================================================================

INSERT INTO tipo_parte (nombre, funcion) VALUES
    -- Tipos del taller (también usados por Reclone)
    ('Promotor',   'Inicia la transcripción'),
    ('RBS',        'Permite el inicio de la traducción'),
    ('CDS',        'Codifica la proteína'),
    ('Terminador', 'Finaliza la transcripción'),
    -- Posiciones ramificadas de Reclone (nombres tomados de los prefijos de sus partes)
    ('BN1',  'RBS/secuencia líder que abre una etiqueta N-terminal (TACT→CCAT)'),
    ('BN2',  'RBS/secuencia líder que abre una etiqueta N-terminal (TACT→GTCA)'),
    ('N1N2', 'Módulo N-terminal N1→N2 (CCAT→GTCA)'),
    ('N1N3', 'Módulo N-terminal N1→N3 (CCAT→TCCA)'),
    ('N1C',  'Módulo N-terminal N1→CDS (CCAT→AATG)'),
    ('N2N3', 'Módulo N-terminal N2→N3 (GTCA→TCCA)'),
    ('N2C',  'Módulo N-terminal N2→CDS (GTCA→AATG)'),
    ('N3C',  'Módulo N-terminal N3→CDS (TCCA→AATG)'),
    ('CD',   'CDS seguido de módulos C-terminales (AATG→AGGT)'),
    ('DN4',  'Módulo C-terminal D→N4 (AGGT→TTCG)'),
    ('DN5',  'Módulo C-terminal D→N5 (AGGT→CGGC)'),
    ('DF',   'Módulo C-terminal que cierra con terminador (AGGT→CGCT)'),
    ('N4N5', 'Módulo C-terminal N4→N5 (TTCG→CGGC)'),
    ('N4E',  'Módulo C-terminal N4→terminador (TTCG→GCTT)'),
    ('N5E',  'Módulo C-terminal N5→terminador (CGGC→GCTT)'),
    ('FA',   'Backbone de E. coli que cierra el círculo (CGCT→GGAG)'),
    -- Posiciones propias del ensamblaje en levadura
    ('Conector izquierdo',   'AConL: abre el ensamblaje en levadura'),
    ('Promotor eucariota',   'Promotor que va directo al ATG, sin RBS (GGAG→AATG)'),
    ('Conector derecho',     'AConR: cierra la unidad de expresión en levadura'),
    ('Brazo homología 3'' / puente',  'Brazo de homología 3'' para integración en el genoma, o puente sin homología en plásmidos episomales'),
    ('Puente sin homología', 'Une AConR con el marcador bacteriano sin brazo ni oriT'),
    ('oriT',                 'Origen de transferencia (conjugación)'),
    ('Marcador bacteriano',  'Resistencia para seleccionar en bacteria'),
    ('Origen de replicación','Origen de replicación en bacteria'),
    ('Brazo homología 5'' / origen de levadura',  'Brazo de homología 5'' (integración) u origen de replicación en levadura (ARS, CEN, 2 micron)'),
    ('Marcador de levadura', 'Marcador de selección en levadura');

INSERT INTO sintaxis (nombre, descripcion) VALUES
    ('Taller 1',
     'Tabla de partes del taller: Promotor GGAG-TACT, RBS TACT-CCAT, CDS CCAT-AGGT, Terminador AGGT-CGCT'),
    ('Taller 1 - Golden Gate',
     'Ejercicio de ensamblaje: RBS termina en AATG (contiene el ATG de inicio), CDS AATG-GCTT'),
    ('Reclone',
     'Sintaxis de las Open DNA Collections de Reclone (E. coli y levadura). Overhangs observados en '
     'las secuencias de github.com/Reclone-org/Open-DNA-Collections; nombres de posición tomados de '
     'los prefijos de sus partes (AB_, BC_, CD_, EF_, N1N2_...)');

INSERT INTO regla_sintaxis (sintaxis_id, tipo_parte_id, orden, overhang_izq, overhang_der)
SELECT s.id, tp.id, r.orden, r.izq, r.der
FROM (VALUES
        ('Taller 1', 'Promotor',   1, 'GGAG', 'TACT'),
        ('Taller 1', 'RBS',        2, 'TACT', 'CCAT'),
        ('Taller 1', 'CDS',        3, 'CCAT', 'AGGT'),
        ('Taller 1', 'Terminador', 4, 'AGGT', 'CGCT'),

        ('Taller 1 - Golden Gate', 'Promotor',   1, 'GGAG', 'TACT'),
        ('Taller 1 - Golden Gate', 'RBS',        2, 'TACT', 'AATG'),
        ('Taller 1 - Golden Gate', 'CDS',        3, 'AATG', 'GCTT'),
        ('Taller 1 - Golden Gate', 'Terminador', 4, 'GCTT', 'CGCT'),

        ('Reclone', 'Conector izquierdo',    1, 'ATGA', 'GGAG'),
        ('Reclone', 'Promotor',              2, 'GGAG', 'TACT'),
        ('Reclone', 'Promotor eucariota',    2, 'GGAG', 'AATG'),
        ('Reclone', 'RBS',                   3, 'TACT', 'AATG'),
        ('Reclone', 'BN1',                   3, 'TACT', 'CCAT'),
        ('Reclone', 'BN2',                   3, 'TACT', 'GTCA'),
        ('Reclone', 'N1N2',                  4, 'CCAT', 'GTCA'),
        ('Reclone', 'N1N3',                  4, 'CCAT', 'TCCA'),
        ('Reclone', 'N1C',                   4, 'CCAT', 'AATG'),
        ('Reclone', 'N2N3',                  5, 'GTCA', 'TCCA'),
        ('Reclone', 'N2C',                   5, 'GTCA', 'AATG'),
        ('Reclone', 'N3C',                   6, 'TCCA', 'AATG'),
        ('Reclone', 'CDS',                   7, 'AATG', 'GCTT'),
        ('Reclone', 'CD',                    7, 'AATG', 'AGGT'),
        ('Reclone', 'DN4',                   8, 'AGGT', 'TTCG'),
        ('Reclone', 'DN5',                   8, 'AGGT', 'CGGC'),
        ('Reclone', 'DF',                    8, 'AGGT', 'CGCT'),
        ('Reclone', 'N4N5',                  9, 'TTCG', 'CGGC'),
        ('Reclone', 'N4E',                   9, 'TTCG', 'GCTT'),
        ('Reclone', 'N5E',                  10, 'CGGC', 'GCTT'),
        ('Reclone', 'Terminador',           11, 'GCTT', 'CGCT'),
        ('Reclone', 'Conector derecho',     12, 'CGCT', 'AGAC'),
        ('Reclone', 'FA',                   12, 'CGCT', 'GGAG'),
        ('Reclone', 'Brazo homología 3'' / puente',  13, 'AGAC', 'CGAA'),
        ('Reclone', 'Puente sin homología', 13, 'AGAC', 'GCAA'),
        ('Reclone', 'oriT',                 14, 'CGAA', 'GCAA'),
        ('Reclone', 'Marcador bacteriano',  15, 'GCAA', 'ACTA'),
        ('Reclone', 'Origen de replicación',16, 'ACTA', 'AAAA'),
        ('Reclone', 'Brazo homología 5'' / origen de levadura',  17, 'AAAA', 'AAGG'),
        ('Reclone', 'Marcador de levadura', 18, 'AAGG', 'ATGA')
     ) AS r(sintaxis, tipo, orden, izq, der)
JOIN sintaxis s    ON s.nombre = r.sintaxis
JOIN tipo_parte tp ON tp.nombre = r.tipo;

-- En E. coli el vector aporta GGAG...CGCT. En levadura el ensamblaje es un
-- plásmido circular completo (incluye marcadores y origen), por eso empieza y
-- termina en el mismo overhang (ATGA).
INSERT INTO vector_destino (nombre, sintaxis_id, overhang_inicio, overhang_fin, resistencia)
SELECT v.nombre, s.id, v.inicio, v.fin, v.resistencia
FROM (VALUES
        ('Vector destino taller',    'Taller 1',               'GGAG', 'CGCT', 'Kanamicina'),
        ('Vector destino GG',        'Taller 1 - Golden Gate', 'GGAG', 'CGCT', 'Kanamicina'),
        ('Reclone E. coli',          'Reclone',                'GGAG', 'CGCT', 'Kanamicina'),
        ('Reclone levadura (circular)', 'Reclone',             'ATGA', 'ATGA', 'Cloranfenicol o espectinomicina')
     ) AS v(nombre, sintaxis, inicio, fin, resistencia)
JOIN sintaxis s ON s.nombre = v.sintaxis;
