"""Compara el diccionario eo-es de aulex.org con la base de datos y añade lo que falta.

Formato de entrada del archivo:  esperanto: traducción1; traducción2; ...

Qué hace:
- Añade a 'entradas' las palabras de esperanto que no existen (fuente = 'aulex').
- Añade a 'es_a_eo_propio' los pares castellano→esperanto que no existen (fuente = 'aulex').
- No duplica nada que ya esté en la base de datos.
- Ignora afijos (líneas que empiezan por '-') y entradas con espacios.

Uso (desde la carpeta del proyecto):
    python tools/importar_aulex.py data/diccionario.db ruta/eo-es.txt
"""
import sqlite3
import sys
from pathlib import Path


def leer_aulex(ruta: Path):
    """Devuelve lista de (eo, [traducciones castellanas])."""
    entradas = []
    with ruta.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or ":" not in linea:
                continue
            eo, _, resto = linea.partition(":")
            eo = eo.strip().lower()
            if not eo or eo.startswith("-") or " " in eo:
                continue
            es = [t.strip().rstrip(".").lower() for t in resto.split(";")]
            es = [t for t in es if t]
            if es:
                entradas.append((eo, es))
    return entradas


def importar(ruta_db: Path, ruta_aulex: Path) -> None:
    con = sqlite3.connect(ruta_db)
    con.execute(
        """CREATE TABLE IF NOT EXISTS es_a_eo_propio (
               es_norm TEXT NOT NULL,
               eo      TEXT NOT NULL,
               fuente  TEXT DEFAULT 'traduccion propia',
               PRIMARY KEY (es_norm, eo))"""
    )

    existentes_eo = {r[0] for r in con.execute("SELECT eo_norm FROM entradas")}
    pares_existentes = {
        (r[0], r[1]) for r in con.execute("SELECT es_norm, eo FROM es_a_eo_propio")
    }

    datos = leer_aulex(ruta_aulex)
    eo_nuevas = pares_nuevos = pares_ya = 0

    for eo, traducciones in datos:
        if eo not in existentes_eo:
            con.execute(
                """INSERT INTO entradas (eo, eo_norm, categoria, es, en, fuente)
                   VALUES (?, ?, NULL, ?, NULL, 'aulex')""",
                (eo, eo, "; ".join(traducciones)),
            )
            existentes_eo.add(eo)
            eo_nuevas += 1

        for es in traducciones:
            if (es, eo) in pares_existentes:
                pares_ya += 1
                continue
            con.execute(
                "INSERT OR IGNORE INTO es_a_eo_propio (es_norm, eo, fuente) VALUES (?, ?, 'aulex')",
                (es, eo),
            )
            pares_existentes.add((es, eo))
            pares_nuevos += 1

    con.commit()
    con.close()
    print(f"Líneas procesadas: {len(datos)}")
    print(f"Palabras de esperanto añadidas al diccionario: {eo_nuevas}")
    print(f"Pares castellano→esperanto añadidos: {pares_nuevos}")
    print(f"Pares que ya existían (no tocados): {pares_ya}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    importar(Path(sys.argv[1]), Path(sys.argv[2]))
