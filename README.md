# Reclone · partes de ADN y ensamblajes Golden Gate

Gestión de partes de ADN (promotores, RBS, CDS, terminadores), sus overhangs
según una sintaxis modular (Reclone) y los constructos ensamblados.
Basado en el *Taller 1: Sintaxis Reclone y diseño de overhangs*.

**Principio:** las reglas del checklist del taller viven en la base de datos
(PostgreSQL), así que ningún dato inválido puede guardarse, venga de la app,
de un script, de un Excel o de alguien escribiendo SQL a mano.

## Estructura

```
db/esquema.sql        tablas, restricciones, trigger de validación y vistas
db/catalogo.sql       tipos de parte, sintaxis, reglas de overhangs y vectores
datos/                CSV de ejemplo (partes del taller y un archivo con errores)
datos/reclone/        placas de las Open DNA Collections (se descargan solas; no van en el repositorio)
reclone/adn.py        lógica de ADN pura: BsaI, complemento, ensamblaje, conteo
reclone/repositorio.py consultas y escrituras en PostgreSQL
reclone/importador.py importación CSV/Excel con reporte de errores por fila
reclone/reclone_org.py descarga e importación de las colecciones de Reclone
reclone/combinaciones.py conteo y enumeración de constructos posibles (grafo de overhangs)
reclone/servidor_local.py servidor PostgreSQL propio del proyecto (carpeta .pg/)
reclone/__main__.py   línea de comandos
app.py                interfaz web (Streamlit)
tests/                pruebas automáticas (pytest)
instalar.bat          instalación local con doble clic (y scripts/verificar_entorno.py)
iniciar.bat           arranca la base de datos y la aplicación
docs/guia.md         guía de uso para personas sin formación en biología
docs/diagrama_esquema.html diagrama entidad-relación
```

## Cómo correrlo (Windows)

Guía de uso para cualquier persona: [docs/guia.md](docs/guia.md) (también está
dentro de la aplicación, en la sección **Guía**).

**Requisitos:** Python 3.10 o superior y PostgreSQL instalado (versión 13 o
superior). Del PostgreSQL solo se usan sus programas; el proyecto crea su propio
servidor en la carpeta `.pg/`, en el puerto 5433, escuchando solo en tu equipo,
así que no toca el servicio de PostgreSQL del sistema ni pide su contraseña.

### La primera vez (una sola vez)

**Opción fácil:** haz doble clic en **`instalar.bat`**. Comprueba que tengas
Python y PostgreSQL, crea el entorno, instala las librerías (si un antivirus
bloquea la descarga, reintenta solo con los certificados de Windows) y carga los
datos. Si lo ejecutas de nuevo, no toca la base que ya exista. Al terminar usa
`iniciar.bat`.

Todo es **local**: la base de datos y la aplicación solo escuchan en
`127.0.0.1`, es decir, no se puede entrar desde otros equipos de la red, y todo
queda dentro de la carpeta del proyecto (`.venv` y `.pg`).

**A mano**, abre PowerShell o una terminal en la carpeta del proyecto y ejecuta:

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m reclone demo
.venv\Scripts\python -m reclone importar-reclone
```

1. Crea un entorno de Python aislado (`.venv`).
2. Instala las librerías.
3. `demo` arranca PostgreSQL, crea las tablas y carga los datos del taller.
4. `importar-reclone` carga las ~300 partes de Reclone. Si no tienes todavía los
   archivos en `datos/reclone/`, los descarga de GitHub (necesita internet).

> `demo` **borra y recrea** la base. Úsalo solo la primera vez o para empezar de
> cero; si ya guardaste constructos propios, no lo vuelvas a ejecutar.

### Cada día

Haz doble clic en **`iniciar.bat`**. Arranca PostgreSQL, abre la aplicación en
http://127.0.0.1:8501 y deja la ventana abierta mientras la uses. Para terminar,
cierra esa ventana. Para apagar también la base de datos:

```bash
.venv\Scripts\python -m reclone db detener
```

Si prefieres hacerlo a mano en vez de con el `.bat`:

```bash
.venv\Scripts\python -m reclone db iniciar
.venv\Scripts\python -m streamlit run app.py
```

Si abres la aplicación y PostgreSQL no está corriendo, aparece un botón
**Iniciar servidor local**.

### Si algo falla

| Síntoma | Causa probable y solución |
|---|---|
| `pip` falla con `CERTIFICATE_VERIFY_FAILED` | Un antivirus (p. ej. Avast) intercepta el tráfico seguro. Instala con `pip install --use-feature=truststore -r requirements.txt` (usa los certificados de Windows, sin desactivar la verificación). |
| `No encontré 'pg_ctl'` / `initdb` | PostgreSQL no está en la ruta habitual. Copia `.env.example` a `.env` y define `PG_BIN` con su carpeta `bin` (p. ej. `C:\Program Files\PostgreSQL\16\bin`). |
| "No hay conexión con PostgreSQL" | El servidor está apagado: `python -m reclone db iniciar` o el botón de la aplicación. |
| Puerto 5433 u 8501 ocupado | Cambia `PG_PUERTO` en `.env`, o usa `streamlit run app.py --server.port 8502`. |
| Cambié código y la aplicación se comporta raro | Streamlit conserva módulos viejos en memoria: cierra y vuelve a abrir `iniciar.bat`. |
| Se apagó el equipo con la base abierta | Normal. Vuelve a ejecutar `db iniciar`; PostgreSQL se recupera solo. |

### Copias de seguridad

Con la base detenida (`db detener`), copia la carpeta `.pg/`. Con la base
encendida, puedes exportarla con `pg_dump`:

```bash
"C:\Program Files\PostgreSQL\16\bin\pg_dump" -h 127.0.0.1 -p 5433 -U reclone -d reclone -f respaldo.sql
```

Para usar un servidor compartido por el equipo en lugar del local, copia
`.env.example` a `.env` y define `DATABASE_URL`.

## Línea de comandos

```bash
python -m reclone db iniciar | detener | estado
python -m reclone esquema [--reiniciar]
python -m reclone importar datos/partes_taller.csv [--parcial]
python -m reclone importar-reclone [--descargar] [--informe omitidas.csv]
python -m reclone combinaciones --vector "Vector destino taller" --con GFP [--desde N --limite 50]
python -m reclone ensamblar Cassette_GG
python -m reclone digerir CGGGTCTCATACTAAAGAGGAGAAAAATGTGAGACCCG
```

## Qué se valida y dónde

| Regla (checklist del taller) | Dónde |
|---|---|
| Overhangs de 4 nt, solo A/C/G/T, no palindrómicos | dominio `overhang` |
| Los overhangs corresponden al tipo de parte en su sintaxis | llave foránea a `regla_sintaxis` |
| Sin sitios BsaI internos (GGTCTC / GAGACC) | `CHECK` en `parte` |
| Orden correcto, vecinos compatibles, extremos del vector, misma sintaxis | trigger `validar_constructo` (al COMMIT) |
| No borrar partes en uso, nombres únicos | llaves foráneas y `UNIQUE` |
| El producto final ya no contiene sitios BsaI | `adn.ensamblar` |

La importación es **todo o nada** por defecto: si una fila falla, no se guarda
ninguna y se informa cada error con su número de fila.

## Pruebas

```bash
.venv\Scripts\python -m pytest
```

Las pruebas de base de datos usan una base aparte (`reclone_test`).

## Datos de Reclone

`importar-reclone` carga las Open DNA Collections de
[Reclone-org/Open-DNA-Collections](https://github.com/Reclone-org/Open-DNA-Collections)
(a donde remite reclone.org para los datos). No se hace scraping de la web.

1. Lee las placas vigentes (las que traen `ODC ID`) desde `datos/reclone/`. Si
   esa carpeta no existe las descarga de GitHub, y con `--descargar` las baja de
   nuevo. Esa carpeta no se incluye en este repositorio (ver licencia, abajo).
2. Por cada plásmido simula el corte con BsaI y toma el fragmento liberado:
   esa es la parte, y sus overhangs determinan el **tipo** según la sintaxis `Reclone`.
3. Cada parte pasa por las mismas restricciones de la base de datos. Lo que no
   se puede clasificar (vectores destino, filas sin secuencia) no se fuerza:
   queda en el informe de omitidas con su motivo.
4. Es idempotente: se puede ejecutar varias veces sin duplicar (se identifica por `ODC ID`).

Con el snapshot probado (commit `291f7a06`): 304 de 329 plásmidos importados y
25 omitidos (19 sin fragmento BsaI, 6 sin secuencia).

**La sintaxis `Reclone` está inferida de los datos**: los overhangs salen de las
secuencias reales y los nombres de posición (AB, BC, CD, N1N2…) de los prefijos
de los nombres de las partes. No hay un documento oficial de Reclone que la
defina en este proyecto; conviene contrastarla con ellos. Cubre E. coli
(GGAG…CGCT) y levadura (plásmido circular ATGA…ATGA).

**Licencia de los datos:** la OpenMTA cubre los materiales físicos; el repositorio
de Reclone no declara licencia para los datos. Por eso las placas **no se
redistribuyen aquí**: cada persona las descarga directamente de Reclone. Antes de
incluirlas o de publicar una base ya cargada, confirmar con Reclone
(coordination@reclone.org).

## Combinaciones y paginación

Las combinaciones no se guardan: se cuentan por programación dinámica y la
número N se reconstruye directamente (`reclone/combinaciones.py`), así que se
puede paginar y saltar a cualquier posición al instante aunque haya billones
(levadura: 3,3×10¹⁴). La interfaz ofrece filtro por partes (con conteo exacto),
paginador y muestra aleatoria. Que dos partes encajen por overhangs no garantiza
que el constructo tenga sentido biológico.

## Notas para quien mantenga el proyecto

- `instalar.bat` e `iniciar.bat` deben seguir siendo **ASCII (sin tildes) y con
  saltos de línea de Windows (CRLF)**: `cmd` lee mal los `.bat` con caracteres
  no ASCII y parte las líneas por la mitad. El `.gitattributes` fija el CRLF.
- Para pasar el proyecto a otra persona sin git, copia todo **menos `.venv`,
  `.pg` y `.env`**: son propios de cada equipo (rutas absolutas, versión de
  PostgreSQL y tus datos). Con git basta con clonar: el `.gitignore` ya los excluye. Tus constructos guardados no viajan; para compartirlos usa el
  respaldo con `pg_dump`.
- Probado solo en Windows 10 con Python 3.11 y PostgreSQL 16.
