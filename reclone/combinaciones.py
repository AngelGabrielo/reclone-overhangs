"""Combinaciones de partes compatibles, sin base de datos.

Las partes son aristas de un grafo cuyos nodos son overhangs. Un constructo
válido es un camino desde el overhang inicial del vector hasta el final, con
orden de posición estrictamente creciente. El número de caminos puede llegar a
billones (levadura), así que no se recorren: se cuentan por programación
dinámica y la combinación número N se obtiene directamente ("unranking"), lo
que permite paginar y muestrear al azar en tiempo constante por fila.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Iterator, NamedTuple


class ParteGrafo(NamedTuple):
    nombre: str
    izq: str
    der: str
    orden: int


class Constructos:
    """Espacio de constructos válidos inicio -> fin que incluyen las partes pedidas."""

    def __init__(self, partes: Iterable[ParteGrafo], inicio: str, fin: str,
                 incluir: Iterable[str] = ()):
        partes = list(partes)
        self.inicio, self.fin = inicio, fin
        self._por_izq: dict[str, list[ParteGrafo]] = defaultdict(list)
        for p in sorted(partes, key=lambda p: (p.orden, p.nombre)):
            self._por_izq[p.izq].append(p)
        pedidas = list(dict.fromkeys(incluir))
        existentes = {p.nombre for p in partes}
        self._bit = {n: 1 << i for i, n in enumerate(pedidas)}
        self._completo = (1 << len(pedidas)) - 1
        self._memo: dict[tuple[str, int, int], int] = {}
        # Si piden una parte que no existe, no hay ningún constructo posible.
        self.total = 0 if any(n not in existentes for n in pedidas) else self._caminos(inicio, 0, 0)

    def _caminos(self, overhang: str, orden: int, mask: int) -> int:
        """Caminos que, desde este nodo, terminan en `fin` con todas las partes pedidas."""
        clave = (overhang, orden, mask)
        if clave not in self._memo:
            n = 1 if (overhang == self.fin and orden > 0 and mask == self._completo) else 0
            for p in self._por_izq.get(overhang, ()):
                if p.orden > orden:
                    n += self._caminos(p.der, p.orden, mask | self._bit.get(p.nombre, 0))
            self._memo[clave] = n
        return self._memo[clave]

    def numero(self, k: int) -> list[str]:
        """La combinación número k (desde 0), en orden determinista."""
        if not 0 <= k < self.total:
            raise IndexError(f"combinación {k} fuera de rango (hay {self.total})")
        overhang, orden, mask, camino = self.inicio, 0, 0, []
        while True:
            if overhang == self.fin and orden > 0 and mask == self._completo:
                if k == 0:
                    return camino
                k -= 1
            for p in self._por_izq.get(overhang, ()):
                if p.orden > orden:
                    nuevo = mask | self._bit.get(p.nombre, 0)
                    c = self._caminos(p.der, p.orden, nuevo)
                    if k < c:
                        camino.append(p.nombre)
                        overhang, orden, mask = p.der, p.orden, nuevo
                        break
                    k -= c
            else:  # pragma: no cover - imposible si total es correcto
                raise IndexError("inconsistencia al reconstruir la combinación")

    def pagina(self, desplazamiento: int, tamano: int) -> list[list[str]]:
        fin = min(desplazamiento + tamano, self.total)
        return [self.numero(k) for k in range(max(desplazamiento, 0), fin)]


def contar(partes: Iterable[ParteGrafo], inicio: str, fin: str) -> int:
    """Número de constructos válidos inicio -> fin (sin enumerarlos)."""
    return Constructos(partes, inicio, fin).total


def enumerar(partes: Iterable[ParteGrafo], inicio: str, fin: str,
             incluir: Iterable[str] = ()) -> Iterator[list[str]]:
    """Genera los constructos válidos, uno a uno (perezoso)."""
    espacio = Constructos(partes, inicio, fin, incluir)
    for k in range(espacio.total):
        yield espacio.numero(k)
