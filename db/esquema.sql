-- =====================================================================
-- Esquema relacional para partes de ADN y ensamblajes Golden Gate
-- según una sintaxis modular (p. ej. Reclone). Motor: PostgreSQL 13+.
--
-- Las reglas del checklist del taller se hacen cumplir aquí, de modo
-- que sea imposible guardar una parte o un constructo inválido, sin
-- importar si los datos llegan desde la app, un script o a mano.
-- =====================================================================

-- Complemento inverso de una secuencia de ADN (ACGT).
CREATE FUNCTION complemento_inverso(s TEXT)
RETURNS TEXT LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT reverse(translate(upper(s), 'ACGT', 'TGCA'))
$$;

-- Un overhang válido: 4 bases y NO palindrómico (un overhang igual a su
-- complemento inverso, como GATC, se puede ligar consigo mismo).
CREATE DOMAIN overhang AS CHAR(4)
    CONSTRAINT overhang_formato CHECK (VALUE ~ '^[ACGT]{4}$')
    CONSTRAINT overhang_no_palindromico CHECK (VALUE <> complemento_inverso(VALUE));

-- ---------------------------------------------------------------------
-- 1. Catálogos
-- ---------------------------------------------------------------------

CREATE TABLE sintaxis (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL CONSTRAINT sintaxis_nombre_unico UNIQUE,
    enzima      TEXT NOT NULL DEFAULT 'BsaI',
    descripcion TEXT
);

CREATE TABLE tipo_parte (
    id      SERIAL PRIMARY KEY,
    nombre  TEXT NOT NULL CONSTRAINT tipo_parte_nombre_unico UNIQUE,
    funcion TEXT
);

-- Qué overhangs lleva cada tipo de parte dentro de una sintaxis y en qué
-- posición (orden) va. Varios tipos pueden compartir orden: son alternativas
-- (p. ej. un RBS con o sin etiqueta N-terminal) y nunca aparecen juntas en un
-- mismo constructo, porque el orden debe ser estrictamente creciente.
CREATE TABLE regla_sintaxis (
    sintaxis_id   INT NOT NULL REFERENCES sintaxis(id),
    tipo_parte_id INT NOT NULL REFERENCES tipo_parte(id),
    orden         SMALLINT NOT NULL CHECK (orden > 0),
    overhang_izq  overhang NOT NULL,
    overhang_der  overhang NOT NULL,
    PRIMARY KEY (sintaxis_id, tipo_parte_id),
    UNIQUE (sintaxis_id, tipo_parte_id, overhang_izq, overhang_der),
    -- Un par de overhangs identifica un único tipo: permite deducir el tipo
    -- de una parte a partir de sus overhangs.
    CONSTRAINT regla_par_unico UNIQUE (sintaxis_id, overhang_izq, overhang_der),
    CONSTRAINT regla_extremos_distintos CHECK (overhang_izq <> overhang_der)
);

-- ---------------------------------------------------------------------
-- 2. Partes de ADN y su almacenamiento
-- ---------------------------------------------------------------------

CREATE TABLE parte (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT NOT NULL CONSTRAINT parte_nombre_unico UNIQUE,
    sintaxis_id   INT  NOT NULL,
    tipo_parte_id INT  NOT NULL,
    overhang_izq  overhang NOT NULL,
    overhang_der  overhang NOT NULL,
    secuencia     TEXT,                     -- secuencia entre overhangs, 5'->3'
    descripcion   TEXT,
    odc_id        TEXT CONSTRAINT parte_odc_unico UNIQUE,   -- ID de Open DNA Collections
    bbf_id        TEXT,                                     -- ID histórico (FreeGenes / BBF10K)
    coleccion     TEXT,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Checklist: "Los overhangs son compatibles".
    CONSTRAINT parte_overhangs_segun_sintaxis
        FOREIGN KEY (sintaxis_id, tipo_parte_id, overhang_izq, overhang_der)
        REFERENCES regla_sintaxis (sintaxis_id, tipo_parte_id, overhang_izq, overhang_der),

    CONSTRAINT parte_secuencia_bases
        CHECK (secuencia IS NULL OR secuencia ~ '^[ACGT]+$'),

    -- Checklist: "No existen sitios internos de BsaI en las partes".
    CONSTRAINT parte_sin_sitio_bsai CHECK (secuencia IS NULL OR (
        (overhang_izq || secuencia || overhang_der) NOT LIKE '%GGTCTC%' AND
        (overhang_izq || secuencia || overhang_der) NOT LIKE '%GAGACC%'
    ))
);

CREATE TABLE plasmido (
    id          SERIAL PRIMARY KEY,
    codigo      TEXT NOT NULL CONSTRAINT plasmido_codigo_unico UNIQUE,
    parte_id    INT  NOT NULL REFERENCES parte(id),
    backbone    TEXT NOT NULL DEFAULT 'pOpen_v3',
    resistencia TEXT NOT NULL,
    ubicacion   TEXT,
    creado_en   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------
-- 3. Vectores destino y constructos
-- ---------------------------------------------------------------------

CREATE TABLE vector_destino (
    id              SERIAL PRIMARY KEY,
    nombre          TEXT NOT NULL CONSTRAINT vector_nombre_unico UNIQUE,
    sintaxis_id     INT  NOT NULL REFERENCES sintaxis(id),
    overhang_inicio overhang NOT NULL,
    overhang_fin    overhang NOT NULL,
    resistencia     TEXT NOT NULL
);

CREATE TABLE constructo (
    id        SERIAL PRIMARY KEY,
    nombre    TEXT NOT NULL CONSTRAINT constructo_nombre_unico UNIQUE,
    vector_id INT  NOT NULL REFERENCES vector_destino(id),
    estado    TEXT NOT NULL DEFAULT 'diseño'
              CONSTRAINT constructo_estado_valido
              CHECK (estado IN ('diseño', 'ensamblado', 'verificado', 'fallido')),
    notas     TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Tabla intermedia N:M (constructo <-> parte) con la posición.
CREATE TABLE constructo_parte (
    constructo_id INT      NOT NULL REFERENCES constructo(id) ON DELETE CASCADE,
    posicion      SMALLINT NOT NULL CHECK (posicion > 0),
    parte_id      INT      NOT NULL REFERENCES parte(id),
    PRIMARY KEY (constructo_id, posicion)
);

CREATE INDEX parte_tipo_idx            ON parte (tipo_parte_id);
CREATE INDEX parte_overhang_izq_idx    ON parte (sintaxis_id, overhang_izq);
CREATE INDEX plasmido_parte_idx        ON plasmido (parte_id);
CREATE INDEX constructo_parte_parte_idx ON constructo_parte (parte_id);

-- ---------------------------------------------------------------------
-- 4. Validación del ensamblaje completo (trigger diferido al COMMIT)
--    Checklist: orden correcto, overhangs compatibles entre vecinos,
--    extremos compatibles con el vector, misma sintaxis.
-- ---------------------------------------------------------------------

CREATE FUNCTION validar_constructo(p_constructo_id INT)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE
    v      RECORD;
    fila   RECORD;
    previo RECORD;
    n      INT := 0;
BEGIN
    SELECT c.nombre AS constructo, vd.* INTO v
    FROM constructo c JOIN vector_destino vd ON vd.id = c.vector_id
    WHERE c.id = p_constructo_id;

    IF NOT FOUND THEN RETURN; END IF;  -- constructo eliminado

    FOR fila IN
        SELECT cp.posicion, p.nombre, p.sintaxis_id, p.overhang_izq, p.overhang_der,
               r.orden, tp.nombre AS tipo
        FROM constructo_parte cp
        JOIN parte p           ON p.id = cp.parte_id
        JOIN tipo_parte tp     ON tp.id = p.tipo_parte_id
        JOIN regla_sintaxis r  ON r.sintaxis_id = p.sintaxis_id
                              AND r.tipo_parte_id = p.tipo_parte_id
        WHERE cp.constructo_id = p_constructo_id
        ORDER BY cp.posicion
    LOOP
        n := n + 1;

        IF fila.posicion <> n THEN
            RAISE EXCEPTION 'Constructo %: las posiciones deben ser 1..N sin huecos (falta la %)',
                v.constructo, n;
        END IF;

        IF fila.sintaxis_id <> v.sintaxis_id THEN
            RAISE EXCEPTION 'Constructo %: la parte % usa otra sintaxis que el vector %',
                v.constructo, fila.nombre, v.nombre;
        END IF;

        IF previo IS NULL THEN
            IF fila.overhang_izq <> v.overhang_inicio THEN
                RAISE EXCEPTION 'Constructo %: % (%) no encaja con el inicio del vector (% vs %)',
                    v.constructo, fila.nombre, fila.tipo, fila.overhang_izq, v.overhang_inicio;
            END IF;
        ELSE
            IF fila.orden <= previo.orden THEN
                RAISE EXCEPTION 'Constructo %: orden incorrecto, % (%) va después de % (%)',
                    v.constructo, fila.nombre, fila.tipo, previo.nombre, previo.tipo;
            END IF;
            IF fila.overhang_izq <> previo.overhang_der THEN
                RAISE EXCEPTION 'Constructo %: % | % no son compatibles (% vs %)',
                    v.constructo, previo.nombre, fila.nombre, previo.overhang_der, fila.overhang_izq;
            END IF;
        END IF;

        previo := fila;
    END LOOP;

    IF n = 0 THEN
        RAISE EXCEPTION 'Constructo %: no tiene partes', v.constructo;
    END IF;

    IF previo.overhang_der <> v.overhang_fin THEN
        RAISE EXCEPTION 'Constructo %: % no cierra con el fin del vector (% vs %)',
            v.constructo, previo.nombre, previo.overhang_der, v.overhang_fin;
    END IF;
END $$;

CREATE FUNCTION trg_validar_constructo()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_TABLE_NAME = 'constructo' THEN
        PERFORM validar_constructo(NEW.id);
    ELSE
        IF TG_OP IN ('UPDATE', 'DELETE') THEN
            PERFORM validar_constructo(OLD.constructo_id);
        END IF;
        IF TG_OP IN ('INSERT', 'UPDATE') THEN
            PERFORM validar_constructo(NEW.constructo_id);
        END IF;
    END IF;
    RETURN NULL;
END $$;

CREATE CONSTRAINT TRIGGER validar_partes_constructo
    AFTER INSERT OR UPDATE OR DELETE ON constructo_parte
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_validar_constructo();

CREATE CONSTRAINT TRIGGER validar_vector_constructo
    AFTER INSERT OR UPDATE OF vector_id ON constructo
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION trg_validar_constructo();

-- ---------------------------------------------------------------------
-- 5. Vistas de lectura
-- ---------------------------------------------------------------------

CREATE VIEW vista_parte AS
SELECT p.id, p.nombre, tp.nombre AS tipo, r.orden, s.nombre AS sintaxis,
       p.overhang_izq, p.overhang_der, p.coleccion, p.odc_id, p.bbf_id,
       length(p.secuencia) AS largo_pb,
       (SELECT count(*) FROM plasmido pl WHERE pl.parte_id = p.id)          AS plasmidos,
       (SELECT count(*) FROM constructo_parte cp WHERE cp.parte_id = p.id)  AS usos,
       p.descripcion, p.secuencia
FROM parte p
JOIN tipo_parte tp    ON tp.id = p.tipo_parte_id
JOIN sintaxis s       ON s.id = p.sintaxis_id
JOIN regla_sintaxis r ON r.sintaxis_id = p.sintaxis_id AND r.tipo_parte_id = p.tipo_parte_id;

CREATE VIEW vista_constructo AS
SELECT c.id,
       c.nombre,
       vd.nombre AS vector,
       s.nombre  AS sintaxis,
       c.estado,
       vd.overhang_inicio || ' | ' ||
       string_agg(p.nombre, ' → ' ORDER BY cp.posicion) ||
       ' | ' || vd.overhang_fin AS ensamblaje,
       c.notas,
       c.creado_en
FROM constructo c
JOIN vector_destino vd   ON vd.id = c.vector_id
JOIN sintaxis s          ON s.id = vd.sintaxis_id
JOIN constructo_parte cp ON cp.constructo_id = c.id
JOIN parte p             ON p.id = cp.parte_id
GROUP BY c.id, vd.nombre, s.nombre, vd.overhang_inicio, vd.overhang_fin;
