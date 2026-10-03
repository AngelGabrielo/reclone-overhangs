"""Línea de comandos: python -m reclone <comando>  (python -m reclone -h para ayuda)."""

from __future__ import annotations

import argparse
import sys

import pandas as pd

from . import adn, config, importador, reclone_org, repositorio, servidor_local
from .repositorio import ErrorValidacion


def cmd_db(args) -> None:
    if args.accion == "iniciar":
        servidor_local.iniciar()
        print(f"PostgreSQL corriendo en 127.0.0.1:{config.PG_PUERTO} (base '{config.PG_BASE}')")
    elif args.accion == "detener":
        servidor_local.detener()
        print("PostgreSQL detenido")
    else:
        estado = "corriendo" if servidor_local.corriendo() else "detenido"
        print(f"Servidor local: {estado} · datos en {config.PG_DATOS}")
        print(f"Conexión: {config.DATABASE_URL}")


def cmd_esquema(args) -> None:
    repositorio.crear_esquema(reiniciar=args.reiniciar)
    print("Esquema y catálogo creados")


def cmd_importar(args) -> None:
    df = importador.leer_archivo(args.archivo)
    r = importador.importar_partes(df, todo_o_nada=not args.parcial)
    if r.errores:
        print(r.errores_df().to_string(index=False))
        print()
    if r.ok:
        print(f"Importadas {r.importadas} de {r.total} partes")
    elif args.parcial:
        print(f"Importadas {r.importadas} de {r.total}; {len(r.errores)} errores (modo parcial)")
    else:
        print(f"No se importó nada: {len(r.errores)} errores en {r.total} filas (modo todo o nada)")
        sys.exit(1)


def cmd_importar_reclone(args) -> None:
    carpeta = reclone_org.DIR_LOCAL
    if args.descargar or not (carpeta / "ORIGEN.txt").exists():
        print(f"Descargando las placas de github.com/{reclone_org.REPO} …")
        commit = reclone_org.descargar(carpeta)
        print(f"Descargado (commit {commit[:10]})\n")
    else:
        print(f"Usando los datos locales de {carpeta} (commit {str(reclone_org.commit_local())[:10]}); "
              "usa --descargar para actualizarlos\n")
    r = reclone_org.importar(carpeta)
    print(f"Plásmidos leídos: {r.leidas}")
    print(f"  importados:      {r.importadas}")
    print(f"  ya existentes:   {r.existentes}")
    print(f"  omitidos:        {len(r.omitidas)}")
    if r.por_tipo:
        tabla = pd.DataFrame([(c, t, n) for (c, t), n in sorted(r.por_tipo.items())],
                             columns=["colección", "tipo deducido", "partes"])
        print("\nImportadas por colección y tipo:\n" + tabla.to_string(index=False))
    if r.omitidas:
        print("\nOmitidas por motivo:")
        for motivo, n in r.motivos().most_common():
            print(f"  {n:4d}  {motivo}")
        if args.informe:
            r.omitidas_df().to_csv(args.informe, index=False, encoding="utf-8-sig")
            print(f"\nDetalle de las omitidas en {args.informe}")


def cmd_demo(args) -> None:
    """Deja la base lista con los datos del taller."""
    if f"127.0.0.1:{config.PG_PUERTO}" in config.DATABASE_URL:
        servidor_local.iniciar()
    repositorio.crear_esquema(reiniciar=True)
    r = importador.importar_partes(importador.leer_archivo(config.DIR_DATOS / "partes_taller.csv"))
    print(f"Partes importadas: {r.importadas}")
    repositorio.crear_constructo("GFP_v1", "Vector destino taller", ["P1", "R1", "GFP", "T1"],
                                 "Primer diseño del taller")
    repositorio.crear_constructo("RFP_v1", "Vector destino taller", ["P1", "R1", "RFP", "T1"],
                                 "GFP reemplazada por RFP: solo cambia el CDS")
    repositorio.crear_constructo("Cassette_GG", "Vector destino GG",
                                 ["Promotor_GG", "RBS_GG", "CDS_GG", "Terminador_GG"],
                                 "Parte D del ejercicio Golden Gate")
    for codigo, parte in [("pOpen-0001", "P1"), ("pOpen-0002", "R1"), ("pOpen-0003", "GFP"),
                          ("pOpen-0004", "T1"), ("pOpen-0005", "RFP")]:
        repositorio.crear_plasmido(codigo, parte, "Ampicilina", ubicacion="Freezer -20 · caja 1")
    print("Constructos de ejemplo: GFP_v1, RFP_v1, Cassette_GG")
    print(pd.Series(repositorio.conteos()).to_string())


def cmd_combinaciones(args) -> None:
    vectores = repositorio.vectores()
    fila = vectores[vectores["nombre"] == args.vector]
    if fila.empty:
        raise ErrorValidacion("Vectores disponibles: " + ", ".join(vectores["nombre"]))
    vector_id = int(fila.iloc[0]["id"])
    espacio = repositorio.espacio_combinaciones(vector_id, args.con)
    print(f"Combinaciones posibles en '{args.vector}': {repositorio.total_combinaciones(vector_id):,}")
    if args.con:
        print(f"Que incluyen {', '.join(args.con)}: {espacio.total:,}")
    caminos = espacio.pagina(args.desde, args.limite)
    if not caminos:
        print(f"(ninguna en ese rango: --desde {args.desde:,} supera las {espacio.total:,} combinaciones)")
        return
    df = repositorio.a_tabla(caminos, list(range(args.desde + 1, args.desde + 1 + len(caminos))))
    print(f"Mostrando de la {args.desde + 1:,} a la {args.desde + len(df):,}")
    print(df.to_string(index=False))


def cmd_ensamblar(args) -> None:
    cab, piezas = repositorio.detalle_constructo(args.constructo)
    r = adn.ensamblar(cab["overhang_inicio"], cab["overhang_fin"], piezas)
    print(f"{cab['nombre']} en {cab['vector']}  [{cab['estado']}]")
    print(" + ".join(f"[{t}]" if e == "cicatriz" else e for e, t in r.segmentos))
    if r.secuencia:
        resumen = adn.resumir(cab["overhang_inicio"], cab["overhang_fin"], piezas)
        print(f"\nSecuencia final 5'->3' ({resumen.total_pb} pb"
              f"{', circular' if resumen.circular else ''}):\n{r.secuencia}")
        marcas = [" "] * len(r.secuencia)
        for a, b in r.cicatrices:
            marcas[a:b] = "^" * (b - a)
        print("".join(marcas) + "   ^ = cicatrices")
    for p in r.problemas:
        print("Aviso:", p)


def cmd_digerir(args) -> None:
    print(adn.dibujar_doble_hebra(args.secuencia), "\n")
    fragmentos = adn.digerir_bsai(args.secuencia)
    if not fragmentos:
        print("No se libera ningún fragmento (se necesitan sitios GGTCTC ... GAGACC hacia adentro)")
    for f in fragmentos:
        print(f"Fragmento (hebra superior): {f.hebra_superior}")
        print(f"  overhang izquierdo 5' (sup.): {f.overhang_izq}")
        print(f"  overhang derecho 5' (inf., 5'->3'): {f.overhang_der_inferior}"
              f"  (en la superior se lee {f.overhang_der})")


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="python -m reclone", description=__doc__)
    sub = p.add_subparsers(dest="comando", required=True)

    s = sub.add_parser("db", help="servidor PostgreSQL local del proyecto")
    s.add_argument("accion", choices=["iniciar", "detener", "estado"])
    s.set_defaults(func=cmd_db)

    s = sub.add_parser("esquema", help="crear tablas y catálogo")
    s.add_argument("--reiniciar", action="store_true", help="BORRA todos los datos y recrea")
    s.set_defaults(func=cmd_esquema)

    s = sub.add_parser("demo", help="reinicia la base y carga los datos del taller")
    s.set_defaults(func=cmd_demo)

    s = sub.add_parser("importar", help="importar partes desde CSV o Excel")
    s.add_argument("archivo")
    s.add_argument("--parcial", action="store_true", help="guardar las filas válidas aunque haya errores")
    s.set_defaults(func=cmd_importar)

    s = sub.add_parser("importar-reclone", help="importar las Open DNA Collections de Reclone")
    s.add_argument("--descargar", action="store_true",
                   help="bajar de nuevo los datos de GitHub (por defecto se usan los locales)")
    s.add_argument("--informe", metavar="ARCHIVO.csv", help="guardar el detalle de las partes omitidas")
    s.set_defaults(func=cmd_importar_reclone)

    s = sub.add_parser("combinaciones", help="constructos válidos posibles")
    s.add_argument("--vector", default="Vector destino taller")
    s.add_argument("--con", nargs="*", default=[], help="partes que deben estar, p. ej. --con GFP")
    s.add_argument("--limite", type=int, default=100, help="filas por página")
    s.add_argument("--desde", type=int, default=0, help="desplazamiento (0 = primera página)")
    s.set_defaults(func=cmd_combinaciones)

    s = sub.add_parser("ensamblar", help="secuencia final de un constructo con sus cicatrices")
    s.add_argument("constructo")
    s.set_defaults(func=cmd_ensamblar)

    s = sub.add_parser("digerir", help="simular el corte con BsaI de una secuencia")
    s.add_argument("secuencia")
    s.set_defaults(func=cmd_digerir)

    args = p.parse_args(argv)
    try:
        args.func(args)
    except (ErrorValidacion, ConnectionError, FileNotFoundError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
