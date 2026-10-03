"""Interfaz web local: streamlit run app.py"""

from __future__ import annotations

import html
import os
import random
import time
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from reclone import adn, config, importador, reclone_org, repositorio, servidor_local
from reclone.repositorio import ErrorValidacion

st.set_page_config(page_title="Reclone · partes y ensamblajes", page_icon="🧬", layout="wide")

ESTADOS = ["diseño", "ensamblado", "verificado", "fallido"]


def avisar_error(e: Exception) -> None:
    st.error(str(e))


COLORES_PARTES = ["#E6F1FB", "#EAF3DE", "#FBEAF0", "#FAEEDA", "#E1F5EE", "#EEEDFE"]


def barra_html(resumen: adn.ResumenPartes) -> str:
    """Barra proporcional: ancho = largo de cada parte, mismos colores que la secuencia."""
    total = resumen.total_pb
    trozos = []
    for i, f in enumerate(resumen.filas):
        ancho = 100 * f["pb"] / total
        texto = html.escape(f["parte"]) if ancho >= 9 else ""
        trozos.append(
            f'<div title="{html.escape(f["parte"])} · {f["pb"]:,} pb ({f["porcentaje"]}%)" '
            f'style="width:{ancho}%;background:{COLORES_PARTES[i % len(COLORES_PARTES)]};color:#2C2C2A;'
            f'overflow:hidden;white-space:nowrap;text-overflow:ellipsis;padding:0 4px;'
            f'box-sizing:border-box;border-right:1px solid #fff">{texto}</div>')
    ancho_c = 100 * resumen.cicatrices_pb / total
    trozos.append(f'<div title="cicatrices: {resumen.cicatrices_pb} pb" '
                  f'style="width:{ancho_c}%;background:#534AB7;min-width:2px"></div>')
    return ('<div style="display:flex;height:30px;border-radius:6px;overflow:hidden;'
            'font:12px system-ui,sans-serif;line-height:30px;border:1px solid #b4b2a9">'
            + "".join(trozos) + "</div>")


def secuencia_html(segmentos: list[tuple[str, str]]) -> str:
    """Secuencia con cicatrices resaltadas y cada parte en su color."""
    colores = COLORES_PARTES
    trozos, k = [], 0
    for etiqueta, texto in segmentos:
        if etiqueta == "cicatriz":
            trozos.append(f'<span title="cicatriz / overhang" style="background:#534AB7;'
                          f'color:#fff;padding:1px 2px;border-radius:3px">{texto}</span>')
        else:
            trozos.append(f'<span title="{html.escape(etiqueta)}" style="background:{colores[k % len(colores)]};'
                          f'color:#2C2C2A">{html.escape(texto)}</span>')
            k += 1
    return ('<div style="font-family:Consolas,monospace;font-size:14px;line-height:1.9;'
            'word-break:break-all">' + "".join(trozos) + "</div>")


# ---------------------------------------------------------------------------
# Apagar todo (solo si se arrancó con iniciar.bat / `python -m reclone app`)
# ---------------------------------------------------------------------------

if os.getenv("RECLONE_LANZADOR"):
    with st.sidebar:
        if st.button("⏻ Apagar todo", width="stretch", key="apagar_todo",
                     help="Cierra la aplicación y apaga la base de datos local"):
            st.warning("Apagando… ya puedes cerrar esta pestaña.")
            time.sleep(0.5)
            os._exit(0)  # el lanzador detecta que la app terminó y apaga PostgreSQL

# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------

try:
    conteos = repositorio.conteos()
except ConnectionError:
    st.title("🧬 Reclone")
    st.warning("PostgreSQL no está corriendo.")
    if st.button("Iniciar servidor local", type="primary"):
        with st.spinner("Iniciando PostgreSQL…"):
            servidor_local.iniciar()
        st.rerun()
    st.stop()
except ErrorValidacion:
    st.title("🧬 Reclone")
    st.warning("La base de datos está vacía: falta crear el esquema.")
    if st.button("Crear esquema y cargar datos del taller", type="primary"):
        from reclone.__main__ import cmd_demo
        cmd_demo(None)
        st.rerun()
    st.stop()

PAGINAS = ["Inicio", "Guía", "Partes", "Importar", "Reclone", "Combinaciones", "Constructos",
           "Plásmidos", "Sintaxis y vectores", "Herramientas ADN", "Diagrama de la BD"]
with st.sidebar:
    st.markdown("## 🧬 Reclone")
    pagina = st.radio("Sección", PAGINAS, label_visibility="collapsed")
    st.caption(f"Base: `{config.DATABASE_URL}`")

# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

if pagina == "Inicio":
    st.title("Partes de ADN y ensamblajes Golden Gate")
    cols = st.columns(4)
    cols[0].metric("Partes", conteos["parte"])
    cols[1].metric("Plásmidos", conteos["plasmido"])
    cols[2].metric("Constructos", conteos["constructo"])
    cols[3].metric("Sintaxis", conteos["sintaxis"])
    st.subheader("Constructos recientes")
    df = repositorio.constructos()
    st.dataframe(df[["nombre", "ensamblaje", "estado", "vector", "notas"]] if not df.empty else df,
                 hide_index=True, width="stretch")
    st.subheader("Filas por tabla")
    st.dataframe(pd.DataFrame(conteos.items(), columns=["tabla", "filas"]), hide_index=True)

elif pagina == "Guía":
    st.markdown((config.RAIZ / "docs" / "guia.md").read_text(encoding="utf-8"))

elif pagina == "Partes":
    st.title("Partes")
    sintaxis = repositorio.sintaxis()["nombre"].tolist()
    tipos = repositorio.tipos_parte()["nombre"].tolist()
    c1, c2, c3 = st.columns(3)
    f_sintaxis = c1.selectbox("Sintaxis", ["(todas)"] + sintaxis)
    f_tipo = c2.selectbox("Tipo", ["(todos)"] + tipos)
    f_texto = c3.text_input("Buscar", placeholder="nombre o descripción")
    df = repositorio.partes(None if f_sintaxis == "(todas)" else f_sintaxis,
                            None if f_tipo == "(todos)" else f_tipo, f_texto)
    st.dataframe(df.drop(columns=["id", "orden"], errors="ignore"), hide_index=True,
                 width="stretch")

    with st.expander("➕ Nueva parte"):
        with st.form("nueva_parte", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            nombre = c1.text_input("Nombre")
            n_sintaxis = c2.selectbox("Sintaxis", sintaxis, key="np_s")
            n_tipo = c3.selectbox("Tipo", tipos, key="np_t")
            regla = repositorio.reglas(n_sintaxis)
            r = regla[regla["tipo"] == n_tipo]
            if not r.empty:
                st.caption(f"Overhangs según la sintaxis: **{r.iloc[0]['overhang_izq']}** … "
                           f"**{r.iloc[0]['overhang_der']}** (se asignan automáticamente)")
            secuencia = st.text_area("Secuencia entre overhangs (5'→3', opcional)")
            descripcion = st.text_input("Descripción")
            if st.form_submit_button("Guardar", type="primary"):
                izq = r.iloc[0]["overhang_izq"] if not r.empty else "AAAA"
                der = r.iloc[0]["overhang_der"] if not r.empty else "AAAA"
                problemas = adn.problemas_parte(izq, adn.normalizar(secuencia), der)
                if not nombre.strip():
                    st.error("Falta el nombre")
                elif problemas:
                    st.error(" · ".join(problemas))
                else:
                    try:
                        repositorio.crear_parte(nombre.strip(), n_tipo, n_sintaxis, secuencia, descripcion)
                        st.success(f"Parte {nombre} guardada")
                        st.rerun()
                    except ErrorValidacion as e:
                        avisar_error(e)

    with st.expander("🗑️ Eliminar parte"):
        if not df.empty:
            borrar = st.selectbox("Parte", df["nombre"], key="del_parte")
            if st.button("Eliminar"):
                try:
                    repositorio.eliminar_parte(borrar)
                    st.rerun()
                except ErrorValidacion as e:
                    avisar_error(e)

elif pagina == "Importar":
    st.title("Importar partes desde CSV o Excel")
    st.markdown("Columnas: `nombre`, `tipo`, `sintaxis` (obligatorias) y `overhang_izq`, "
                "`overhang_der`, `secuencia`, `descripcion` (opcionales; si faltan los overhangs "
                "se toman de la sintaxis).")
    plantilla = (config.DIR_DATOS / "partes_taller.csv").read_bytes()
    st.download_button("Descargar plantilla de ejemplo", plantilla, "plantilla_partes.csv", "text/csv")
    archivo = st.file_uploader("Archivo", type=["csv", "xlsx"])
    todo_o_nada = st.toggle("Todo o nada (si hay un error no se guarda ninguna fila)", value=True)
    if archivo:
        try:
            df = importador.leer_archivo(archivo, archivo.name)
            st.dataframe(df, hide_index=True, width="stretch")
            if st.button(f"Importar {len(df)} filas", type="primary"):
                r = importador.importar_partes(df, todo_o_nada)
                if r.ok:
                    st.success(f"Importadas {r.importadas} de {r.total} partes")
                else:
                    if todo_o_nada:
                        st.error(f"No se importó nada: {len(r.errores)} errores")
                    else:
                        st.warning(f"Importadas {r.importadas} de {r.total}; {len(r.errores)} errores")
                    st.dataframe(r.errores_df(), hide_index=True, width="stretch")
        except ErrorValidacion as e:
            avisar_error(e)

elif pagina == "Reclone":
    st.title("Open DNA Collections de Reclone")
    st.markdown(
        f"Importa las placas oficiales de [github.com/{reclone_org.REPO}]"
        f"(https://github.com/{reclone_org.REPO}). Para cada plásmido se simula el corte con BsaI, "
        "se leen los overhangs y se deduce el tipo según la sintaxis **Reclone**. Lo que no se "
        "puede clasificar queda en el informe, no se fuerza.")
    local = reclone_org.commit_local()
    st.caption(f"Datos locales: commit `{local[:10]}`" if local else "Aún no hay datos locales.")
    c1, c2 = st.columns(2)
    bajar = c1.button("Descargar de nuevo desde GitHub", disabled=False)
    ir = c2.button("Importar a la base de datos", type="primary")
    if bajar:
        with st.spinner("Descargando…"):
            st.success(f"Descargado (commit {reclone_org.descargar(avisar=lambda *_: None)[:10]})")
    if ir:
        try:
            with st.spinner("Importando…"):
                r = reclone_org.importar()
            st.success(f"Importados {r.importadas} · ya existentes {r.existentes} · "
                       f"omitidos {len(r.omitidas)} (de {r.leidas} leídos)")
            if r.por_tipo:
                st.dataframe(pd.DataFrame([(c, t, n) for (c, t), n in sorted(r.por_tipo.items())],
                                          columns=["colección", "tipo deducido", "partes"]),
                             hide_index=True, width="stretch")
            if r.omitidas:
                st.subheader("Omitidas")
                st.dataframe(r.omitidas_df(), hide_index=True, width="stretch")
        except (ErrorValidacion, FileNotFoundError, RuntimeError, OSError) as e:
            avisar_error(e)

elif pagina == "Combinaciones":
    st.title("Combinaciones posibles")
    st.caption("Constructos válidos que se pueden armar con las partes existentes. No se guardan en "
               "la base: se calculan recorriendo los overhangs compatibles. Con millones de "
               "combinaciones conviene filtrar por partes, paginar o ver una muestra aleatoria.")
    vectores = repositorio.vectores()
    vector = st.selectbox("Vector destino", vectores["nombre"])
    fila = vectores[vectores["nombre"] == vector].iloc[0]
    partes_sintaxis = repositorio.partes(fila["sintaxis"])
    incluir = st.multiselect("Deben incluir", partes_sintaxis["nombre"])
    espacio = repositorio.espacio_combinaciones(int(fila["id"]), incluir)
    total_vector = repositorio.total_combinaciones(int(fila["id"])) if incluir else espacio.total
    c1, c2 = st.columns(2)
    c1.metric("Total posibles en este vector", f"{total_vector:,}")
    c2.metric("Que cumplen el filtro" if incluir else "Mostrando todas", f"{espacio.total:,}")

    combos = pd.DataFrame()
    if espacio.total == 0:
        st.info("Ninguna combinación válida incluye todas esas partes a la vez "
                "(p. ej. dos partes de la misma posición no pueden convivir).")
    else:
        c1, c2, c3 = st.columns([1, 1.3, 1.3])
        tamano = c1.selectbox("Filas por página", [25, 50, 100, 250, 500], index=1)
        aleatoria = c3.toggle("Muestra aleatoria", help="Útil cuando hay millones de combinaciones")
        if aleatoria:
            if "semilla" not in st.session_state:
                st.session_state["semilla"] = 0
            if c2.button("🎲 Otra muestra", width="stretch"):
                st.session_state["semilla"] += 1
            azar = random.Random(st.session_state["semilla"])
            numeros = sorted({azar.randrange(espacio.total) for _ in range(min(tamano, espacio.total))})
            caminos = [espacio.numero(k) for k in numeros]
            st.caption(f"{len(caminos)} combinaciones al azar de {espacio.total:,}")
        else:
            paginas = -(-espacio.total // tamano)
            clave = f"pag|{vector}|{'|'.join(incluir)}|{tamano}"
            pagina_n = c2.number_input("Página", 1, min(paginas, 2**53 - 1), 1, key=clave)
            desde = (pagina_n - 1) * tamano
            caminos = espacio.pagina(desde, tamano)
            numeros = list(range(desde, desde + len(caminos)))
            st.caption(f"Combinaciones {desde + 1:,} a {desde + len(caminos):,} de {espacio.total:,} "
                       f"· página {pagina_n:,} de {paginas:,}")
        combos = repositorio.a_tabla(caminos, [k + 1 for k in numeros])

    sel = st.dataframe(combos, hide_index=True, width="stretch",
                       on_select="rerun", selection_mode="single-row")
    filas_sel = sel.selection.rows
    if filas_sel:
        elegidas = [x for x in combos.iloc[filas_sel[0]].tolist() if isinstance(x, str)]
        st.markdown("**Guardar como constructo:** " + " → ".join(elegidas))
        c1, c2 = st.columns([2, 1])
        nombre = c1.text_input("Nombre del constructo", value=repositorio.nombre_sugerido(),
                               help="Código corto y único; la composición queda en las notas.")
        if c2.button("Guardar", type="primary"):
            try:
                n_comb = combos.iloc[filas_sel[0]].get("N.º")
                nota = f"Combinación n.º {int(n_comb):,} de «{vector}»" if n_comb is not None else None
                repositorio.crear_constructo(nombre.strip(), vector, elegidas, nota)
                st.success(f"Constructo {nombre} guardado")
            except ErrorValidacion as e:
                avisar_error(e)

elif pagina == "Constructos":
    st.title("Constructos")
    df = repositorio.constructos()
    if df.empty:
        st.info("Aún no hay constructos. Créalos aquí abajo o desde Combinaciones.")
    else:
        st.dataframe(df[["nombre", "ensamblaje", "estado", "vector", "sintaxis", "notas", "creado_en"]],
                     hide_index=True, width="stretch")
        info = df.set_index("nombre")
        elegido = st.selectbox(
            "Ver detalle", df["nombre"],
            format_func=lambda n: f"{n}  ·  {info.loc[n, 'vector']}  ·  {info.loc[n, 'estado']}")
        cab, piezas = repositorio.detalle_constructo(elegido)
        r = adn.ensamblar(cab["overhang_inicio"], cab["overhang_fin"], piezas)
        resumen = adn.resumir(cab["overhang_inicio"], cab["overhang_fin"], piezas)
        st.markdown(" ".join(f"`{t}`" if e == "cicatriz" else f"**{e}**" for e, t in r.segmentos))

        st.subheader("Resumen por parte")
        if resumen.total_pb:
            st.html(barra_html(resumen))
        tabla = pd.DataFrame(resumen.filas).rename(columns={
            "posicion": "Pos.", "parte": "Parte", "tipo": "Tipo", "overhangs": "Overhangs",
            "pb": "Largo (pb)", "porcentaje": "% del total"})
        tabla["Pos."] = tabla["Pos."].astype(str)
        n_cic = len(piezas) + (0 if resumen.circular else 1)
        tabla.loc[len(tabla)] = ["", f"Cicatrices ({n_cic} × 4 pb)", "", "", resumen.cicatrices_pb,
                                 round(100 * resumen.cicatrices_pb / resumen.total_pb, 1)
                                 if resumen.total_pb else None]
        tabla.loc[len(tabla)] = ["", "TOTAL" + (" (plásmido circular)" if resumen.circular else ""),
                                 "", "", resumen.total_pb, 100.0 if resumen.total_pb else None]
        st.dataframe(tabla, hide_index=True, width="stretch", height="content")
        if resumen.total_pb is None:
            st.caption("No se puede calcular el total: a alguna parte le falta la secuencia.")

        if r.secuencia:
            nota = ""
            if resumen.circular:
                nota = (f" · plásmido circular: el overhang `{cab['overhang_inicio']}` es el mismo en "
                        f"ambos extremos, por eso la secuencia mostrada ({len(r.secuencia):,} "
                        "caracteres) lo repite")
            st.markdown(f"Secuencia final 5'→3' · **{resumen.total_pb:,} pb**{nota} "
                        "(en morado, las cicatrices que dejan los overhangs)")
        st.html(secuencia_html(r.segmentos))
        if r.secuencia:
            st.code(r.secuencia, language=None, wrap_lines=True)
        for p in r.problemas:
            st.warning(p)
        c1, c2, c3 = st.columns([1, 2, 1])
        estado = c1.selectbox("Estado", ESTADOS, index=ESTADOS.index(cab["estado"]))
        notas = c2.text_input("Notas", value=cab["notas"] or "")
        if c3.button("Actualizar", width="stretch"):
            repositorio.actualizar_estado(elegido, estado, notas)
            st.rerun()
        if st.button(f"Eliminar {elegido}"):
            repositorio.eliminar_constructo(elegido)
            st.rerun()

    with st.expander("➕ Nuevo constructo a mano"):
        vectores = repositorio.vectores()
        vector = st.selectbox("Vector", vectores["nombre"], key="nc_v")
        sint = vectores[vectores["nombre"] == vector].iloc[0]["sintaxis"]
        partes_s = repositorio.partes(sint)
        st.caption("Elige las partes en el orden del ensamblaje; la base de datos valida "
                   "el orden y los overhangs al guardar.")
        opciones = [f"{r.nombre}  ·  {r.tipo}  ({r.overhang_izq}→{r.overhang_der})"
                    for r in partes_s.itertuples()]
        marcadas = st.multiselect("Partes", opciones, key="nc_partes")
        elegidas = [m.split("  ·  ")[0] for m in marcadas]
        nombre = st.text_input("Nombre", value=repositorio.nombre_sugerido(), key="nc_nombre")
        if st.button("Crear constructo", type="primary"):
            try:
                repositorio.crear_constructo(nombre.strip(), vector, elegidas)
                st.success("Constructo creado")
                st.rerun()
            except ErrorValidacion as e:
                avisar_error(e)

elif pagina == "Plásmidos":
    st.title("Plásmidos de almacenamiento")
    st.dataframe(repositorio.plasmidos(), hide_index=True, width="stretch")
    with st.expander("➕ Nuevo plásmido"):
        with st.form("nuevo_plasmido"):
            c1, c2, c3 = st.columns(3)
            codigo = c1.text_input("Código del stock")
            parte = c2.selectbox("Parte", repositorio.partes()["nombre"])
            backbone = c3.text_input("Backbone", value="pOpen_v3")
            c1, c2 = st.columns(2)
            resistencia = c1.text_input("Resistencia", value="Ampicilina")
            ubicacion = c2.text_input("Ubicación")
            if st.form_submit_button("Guardar", type="primary"):
                try:
                    repositorio.crear_plasmido(codigo.strip(), parte, resistencia, backbone, ubicacion)
                    st.rerun()
                except ErrorValidacion as e:
                    avisar_error(e)

elif pagina == "Sintaxis y vectores":
    st.title("Sintaxis, reglas y vectores")
    st.dataframe(repositorio.sintaxis(), hide_index=True, width="stretch")
    st.subheader("Reglas de overhangs por posición")
    st.dataframe(repositorio.reglas(), hide_index=True, width="stretch")
    st.subheader("Vectores destino")
    st.dataframe(repositorio.vectores(), hide_index=True, width="stretch")

elif pagina == "Herramientas ADN":
    st.title("Herramientas de ADN")
    st.subheader("Simular el corte con BsaI")
    region = st.text_input("Región (hebra superior, 5'→3')",
                           value="CGGGTCTCATACTAAAGAGGAGAAAAATGTGAGACCCG")
    if region:
        st.code(adn.dibujar_doble_hebra(region), language=None)
        sitios = adn.sitios_bsai(adn.normalizar(region))
        st.caption("Sitios BsaI: " + (", ".join(f"pos. {p + 1} (hebra {h})" for p, h in sitios) or "ninguno"))
        for f in adn.digerir_bsai(region):
            c1, c2, c3 = st.columns(3)
            c1.metric("Overhang izquierdo (sup.)", f.overhang_izq)
            c2.metric("Overhang derecho (inf., 5'→3')", f.overhang_der_inferior)
            c3.metric("Largo del fragmento", f"{len(f.hebra_superior)} nt")
            st.code(f"Fragmento liberado (sup.): {f.hebra_superior}\n"
                    f"Inserto sin overhangs:     {f.inserto}", language=None)
    st.subheader("Complemento inverso")
    s = st.text_input("Secuencia", value="AATG")
    if s:
        st.code(adn.complemento_inverso(adn.normalizar(s)), language=None)

elif pagina == "Diagrama de la BD":
    st.title("Diagrama entidad-relación")
    diagrama = Path(config.RAIZ / "docs" / "diagrama_esquema.html")
    components.html(diagrama.read_text(encoding="utf-8"), height=1650, scrolling=True)
