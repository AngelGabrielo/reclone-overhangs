# Guía rápida

Esta guía explica la aplicación sin necesidad de saber biología.

## La idea en 30 segundos

El ADN es una cadena de letras (A, C, G, T) que funciona como un conjunto de
instrucciones. Para que una bacteria o una levadura fabrique algo (por ejemplo
una proteína que brilla en verde) hay que escribirle esas instrucciones en el
orden correcto.

Los biólogos no las escriben desde cero: usan **piezas estándar** que ya existen
y las ensamblan, como en un juego de construcción. Esta aplicación es el
**catálogo de esas piezas** y el **verificador de las construcciones**.

| Término | Qué es (con una analogía) |
|---|---|
| **Parte** | Una pieza de ADN con una función: un interruptor de encendido (promotor), la receta de la proteína (gen o CDS), una señal de fin (terminador)... |
| **Overhang (conector)** | Las 4 letras en cada extremo de una pieza: el "enchufe" de un LEGO. Dos piezas solo encajan si el enchufe de una es igual al de la otra, así se arma solo en el orden correcto. |
| **Sintaxis** | El reglamento que dice qué enchufe va en cada posición. Si todos los laboratorios usan el mismo (aquí, el de Reclone), sus piezas son intercambiables. |
| **Constructo** | La construcción terminada: varias piezas pegadas en orden. |
| **Plásmido** | Un anillo pequeño de ADN. Sirve como "tubo" donde se guarda una pieza o se entrega una construcción. |
| **Vector** | La "base" sobre la que se construye. |
| **Cicatriz** | Las 4 letras que quedan en cada unión entre piezas: la marca del pegamento. |
| **BsaI** | Las "tijeras" que cortan el ADN dejando justo esos enchufes de 4 letras. |
| **pb** | Pares de bases: la unidad de longitud. 1.000 pb son 1.000 letras. |

## Qué hace cada sección

**Inicio.** El tablero: cuántas piezas, plásmidos y construcciones hay guardadas
y las construcciones más recientes.

**Partes.** El catálogo de piezas. Puedes buscar, filtrar por tipo y ver con qué
enchufes termina cada una. Aquí también se añaden o se borran piezas. La base de
datos no deja guardar una pieza con enchufes que no corresponden a su tipo.

**Importar.** Carga muchas piezas a la vez desde un Excel o un CSV. Si una fila
tiene un error, avisa cuál es y no guarda nada a medias.

**Reclone.** Trae al catálogo las piezas oficiales de Reclone, una colaboración
internacional que reúne material biológico abierto (unas 300 piezas reales con
sus secuencias). Lo que no se puede clasificar, como los vectores vacíos, queda
aparte con su motivo.

**Combinaciones.** Responde a "¿qué construcciones puedo armar con lo que
tengo?". Busca todas las formas de encadenar piezas cuyos enchufes encajan. Con
levadura salen cientos de billones, así que puedes filtrar por las piezas que
quieras sí o sí, pasar de página o ver una muestra al azar. Aquí no se guarda
nada: solo se explora. Al elegir una fila puedes guardarla como constructo.

**Constructos.** Las construcciones que decides guardar. Para cada una muestra el
orden de las piezas, un resumen del largo de cada una (con barra de colores), la
secuencia final completa y las cicatrices. Puedes marcar su estado: en diseño,
ensamblado, verificado o fallido.

**Plásmidos.** El inventario físico: en qué tubo y en qué lugar del congelador
está guardada cada pieza y con qué antibiótico se cultiva.

**Sintaxis y vectores.** El reglamento: qué enchufe lleva cada tipo de pieza en
cada posición, y los vectores disponibles. En bacteria el vector aporta los
extremos y solo se arma el casete; en levadura la construcción es un anillo
completo que incluye todo.

**Herramientas ADN.** Simula las tijeras (BsaI): pegas una secuencia y te enseña
dónde corta y qué enchufes deja en cada extremo.

**Diagrama de la BD.** El mapa de cómo se organiza la información guardada.
Es para quien mantiene el sistema.

## Un flujo típico

1. En **Partes** o **Reclone**, revisa qué piezas hay.
2. En **Combinaciones**, elige un vector y filtra por la pieza que te interesa
   (por ejemplo un gen concreto).
3. Elige una fila y pulsa **Guardar**: queda como constructo con un código corto
   (`CON-0001`) y una nota con su origen.
4. En **Constructos**, revisa el resumen de largos y la secuencia final, y ve
   cambiando su estado a medida que avanza el trabajo en el laboratorio.

## Para qué sirve todo junto

Para **no equivocarse**. En el laboratorio, un enchufe equivocado o una pieza
mal ordenada significan semanas perdidas. Aquí el programa revisa esas reglas
antes de guardar, así que lo que queda registrado siempre es una construcción
que, sobre el papel, se puede armar.

**Límite importante:** que las piezas *encajen* no garantiza que la construcción
*funcione* o tenga sentido biológico (por ejemplo, mezclar piezas de bacteria
con piezas de levadura). Eso lo sigue decidiendo una persona con conocimiento.
