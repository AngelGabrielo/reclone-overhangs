"""Lógica de ADN pura (sin base de datos): validaciones, BsaI y ensamblaje.

Convenciones del taller:
- BsaI reconoce 5'-GGTCTC-3', deja 1 nt espaciador y corta 1 nt después del
  sitio en la hebra que lo contiene y 5 nt después en la complementaria,
  dejando un overhang de 4 nt en 5'.
- Las secuencias se escriben 5'->3' en la hebra superior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

SITIO_BSAI = "GGTCTC"
SITIO_BSAI_INV = "GAGACC"  # complemento inverso: el sitio en la hebra inferior
_COMPLEMENTO = str.maketrans("ACGT", "TGCA")
_BASES = re.compile(r"^[ACGT]+$")
_OVERHANG = re.compile(r"^[ACGT]{4}$")


def normalizar(secuencia: str | None) -> str:
    """Quita espacios/saltos de línea y pasa a mayúsculas."""
    return re.sub(r"\s+", "", secuencia or "").upper()


def complemento(secuencia: str) -> str:
    return secuencia.translate(_COMPLEMENTO)


def complemento_inverso(secuencia: str) -> str:
    return complemento(secuencia)[::-1]


def es_secuencia_valida(secuencia: str) -> bool:
    return bool(_BASES.match(secuencia))


def es_overhang_valido(overhang: str) -> bool:
    return bool(_OVERHANG.match(overhang))


def es_palindromico(overhang: str) -> bool:
    """Un overhang igual a su complemento inverso (p. ej. GATC) se liga consigo mismo."""
    return overhang == complemento_inverso(overhang)


def sitios_bsai(secuencia: str) -> list[tuple[int, str]]:
    """Posiciones (0-based) de sitios BsaI y la hebra donde se leen ('+' o '-')."""
    sitios = [(m.start(), "+") for m in re.finditer(f"(?={SITIO_BSAI})", secuencia)]
    sitios += [(m.start(), "-") for m in re.finditer(f"(?={SITIO_BSAI_INV})", secuencia)]
    return sorted(sitios)


def problemas_overhang(overhang: str) -> list[str]:
    if not es_overhang_valido(overhang):
        return [f"overhang '{overhang}' inválido: deben ser 4 bases A/C/G/T"]
    if es_palindromico(overhang):
        return [f"overhang {overhang} es palindrómico (se liga consigo mismo)"]
    return []


def problemas_parte(overhang_izq: str, secuencia: str, overhang_der: str) -> list[str]:
    """Lista de problemas de una parte (vacía si está bien)."""
    problemas = problemas_overhang(overhang_izq) + problemas_overhang(overhang_der)
    if secuencia and not es_secuencia_valida(secuencia):
        invalidas = sorted(set(secuencia) - set("ACGT"))
        problemas.append(f"la secuencia contiene bases inválidas: {', '.join(invalidas)}")
    elif secuencia:
        for pos, hebra in sitios_bsai(overhang_izq + secuencia + overhang_der):
            problemas.append(f"sitio BsaI interno en la posición {pos + 1} (hebra {hebra})")
    return problemas


# ---------------------------------------------------------------------------
# Digestión con BsaI (parte A del taller)
# ---------------------------------------------------------------------------

@dataclass
class Fragmento:
    """Fragmento liberado por BsaI entre un sitio '+' y el siguiente sitio '-'."""

    inicio: int                  # índice en la hebra superior donde empieza el overhang izq.
    fin: int                     # índice (exclusivo) donde termina el overhang der.
    hebra_superior: str          # incluye ambos overhangs
    overhang_izq: str            # 5' overhang de la hebra superior
    overhang_der: str            # leído en la hebra superior
    overhang_der_inferior: str   # el mismo, leído 5'->3' en la hebra inferior

    @property
    def inserto(self) -> str:
        return self.hebra_superior[4:-4]


def digerir_bsai(secuencia: str) -> list[Fragmento]:
    """Simula el corte con BsaI de una región lineal con sitios apuntando hacia adentro.

    Cada sitio GGTCTC (hebra +) corta hacia la derecha: hebra superior en
    i+7, inferior en i+11 -> overhang izquierdo = sup[i+7:i+11].
    Cada sitio GAGACC (es GGTCTC en la hebra -) corta hacia la izquierda:
    inferior en j-1, superior en j-5 -> overhang derecho = sup[j-5:j-1].
    """
    secuencia = normalizar(secuencia)
    sitios = sitios_bsai(secuencia)
    fragmentos = []
    for k, (i, hebra) in enumerate(sitios):
        if hebra != "+":
            continue
        siguiente = next(((j, h) for j, h in sitios[k + 1:] if h == "-"), None)
        if siguiente is None:
            break
        j = siguiente[0]
        inicio, fin = i + len(SITIO_BSAI) + 1, j - 1
        if fin - inicio < 8:
            continue  # los sitios están demasiado cerca para liberar un fragmento
        superior = secuencia[inicio:fin]
        fragmentos.append(Fragmento(
            inicio=inicio,
            fin=fin,
            hebra_superior=superior,
            overhang_izq=superior[:4],
            overhang_der=superior[-4:],
            overhang_der_inferior=complemento_inverso(superior[-4:]),
        ))
    return fragmentos


def dibujar_doble_hebra(secuencia: str) -> str:
    """Las dos hebras alineadas (5'->3' arriba, 3'->5' abajo)."""
    secuencia = normalizar(secuencia)
    return f"5'-{secuencia}-3'\n3'-{complemento(secuencia)}-5'"


# ---------------------------------------------------------------------------
# Ensamblaje (parte D del taller)
# ---------------------------------------------------------------------------

@dataclass
class PiezaEnsamblaje:
    nombre: str
    overhang_izq: str
    secuencia: str | None
    overhang_der: str
    tipo: str = ""


@dataclass
class ResultadoEnsamblaje:
    secuencia: str | None                 # None si falta la secuencia de alguna parte
    cicatrices: list[tuple[int, int]]     # tramos (inicio, fin) de los overhangs
    segmentos: list[tuple[str, str]]      # (etiqueta, texto) en orden, para mostrar
    problemas: list[str]


def ensamblar(overhang_inicio: str, overhang_fin: str,
              piezas: list[PiezaEnsamblaje]) -> ResultadoEnsamblaje:
    """Secuencia final 5'->3' del cassette tal como queda en el vector.

    El vector aporta overhang_inicio y overhang_fin; entre partes quedan los
    overhangs compartidos como "cicatrices".
    """
    problemas = []
    if not piezas:
        return ResultadoEnsamblaje(None, [], [], ["no hay partes"])

    if piezas[0].overhang_izq != overhang_inicio:
        problemas.append(f"{piezas[0].nombre} no encaja con el inicio del vector "
                         f"({piezas[0].overhang_izq} vs {overhang_inicio})")
    for a, b in zip(piezas, piezas[1:]):
        if a.overhang_der != b.overhang_izq:
            problemas.append(f"{a.nombre} | {b.nombre} no son compatibles "
                             f"({a.overhang_der} vs {b.overhang_izq})")
    if piezas[-1].overhang_der != overhang_fin:
        problemas.append(f"{piezas[-1].nombre} no cierra con el fin del vector "
                         f"({piezas[-1].overhang_der} vs {overhang_fin})")

    segmentos = [("cicatriz", overhang_inicio)]
    for pieza in piezas:
        segmentos.append((pieza.nombre, pieza.secuencia or f"[{pieza.nombre}: sin secuencia]"))
        segmentos.append(("cicatriz", pieza.overhang_der))

    faltantes = [p.nombre for p in piezas if not p.secuencia]
    if faltantes:
        problemas.append("faltan secuencias de: " + ", ".join(faltantes))
        return ResultadoEnsamblaje(None, [], segmentos, problemas)

    secuencia, cicatrices = "", []
    for etiqueta, texto in segmentos:
        if etiqueta == "cicatriz":
            cicatrices.append((len(secuencia), len(secuencia) + len(texto)))
        secuencia += texto

    # El producto correcto ya no debe contener sitios BsaI.
    for pos, hebra in sitios_bsai(secuencia):
        problemas.append(f"el producto conserva un sitio BsaI en {pos + 1} (hebra {hebra})")

    return ResultadoEnsamblaje(secuencia, cicatrices, segmentos, problemas)


@dataclass
class ResumenPartes:
    filas: list[dict]            # una por parte: posicion, parte, tipo, overhangs, pb, porcentaje
    cicatrices_pb: int
    total_pb: int | None         # None si a alguna parte le falta la secuencia
    circular: bool               # el vector empieza y termina en el mismo overhang


def resumir(overhang_inicio: str, overhang_fin: str,
            piezas: list[PiezaEnsamblaje]) -> ResumenPartes:
    """Largo que aporta cada parte y el total real del constructo.

    Cada parte aporta su inserto (sin overhangs); los overhangs (cicatrices) se
    cuentan aparte: n+1 de 4 pb. En un plásmido circular (inicio == fin) el
    overhang del extremo es el mismo y se cuenta una sola vez.
    """
    circular = overhang_inicio == overhang_fin
    cicatrices = 4 * (len(piezas) + 1) - (4 if circular else 0)
    completo = all(p.secuencia for p in piezas)
    total = (sum(len(p.secuencia) for p in piezas) + cicatrices) if completo and piezas else None
    filas = []
    for i, p in enumerate(piezas, start=1):
        largo = len(p.secuencia) if p.secuencia else None
        filas.append({
            "posicion": i, "parte": p.nombre, "tipo": p.tipo,
            "overhangs": f"{p.overhang_izq}→{p.overhang_der}", "pb": largo,
            "porcentaje": round(100 * largo / total, 1) if largo and total else None})
    return ResumenPartes(filas, cicatrices, total, circular)
