"""Carga las traducciones propias (traducciones/*.csv, formato eo;es) en la base SQLite.

Para cada línea:
- Normaliza espacios y mayúsculas.
- Comprueba que la palabra en esperanto exista en la tabla 'entradas' (volcado de kaikki.org).
- Descarta duplicados y palabras con caracteres no latinos (p. ej. una 'о' cirílica).
- Marca el origen como 'traduccion propia' para distinguirlo de Wiktionary.

Uso (desde la carpeta del proyecto):
    python tools/importar_raices.py data/diccionario.db traducciones
"""
import csv
import re
import sqlite3
import sys
from pathlib import Path

SOLO_LATINO = re.compile(r"^[A-Za-zĈĉĜĝĤĥĴĵŜŝŬŭ' -]+$")


def cargar_csv(carpeta: Path):
    for ruta in sorted(carpeta.glob("*.csv")):
        with ruta.open(encoding="utf-8") as f:
            for n, fila in enumerate(csv.reader(f, delimiter=";"), start=1):
                if len(fila) != 2:
                    print(f"  [{ruta.name}:{n}] formato incorrecto, se ignora: {fila}")
                    continue
                yield ruta.name, n, fila[0].strip().lower(), fila[1].strip().lower()


def importar(ruta_db: Path, carpeta: Path) -> None:
    con = sqlite3.connect(ruta_db)
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute(
        """CREATE TABLE IF NOT EXISTS es_a_eo_propio (
               es_norm TEXT NOT NULL,
               eo      TEXT NOT NULL,
               fuente  TEXT DEFAULT 'traduccion propia',
               PRIMARY KEY (es_norm, eo))"""
    )

    existentes = {r[0] for r in con.execute("SELECT eo_norm FROM entradas")}
    vistos = set()
    ok = descartadas = 0

    for archivo, n, eo, es in cargar_csv(carpeta):
        if not eo or not es:
            continue
        # El esperanto solo puede llevar letras latinas (sin cirílicas). El castellano lleva tildes y ñ.
        if not SOLO_LATINO.match(eo):
            print(f"  [{archivo}:{n}] caracteres no válidos en esperanto: {eo} / {es}")
            descartadas += 1
            continue
        if eo not in existentes:
            print(f"  [{archivo}:{n}] no existe en el diccionario de esperanto: {eo}")
            descartadas += 1
            continue
        if (es, eo) in vistos:
            continue
        vistos.add((es, eo))
        con.execute(
            "INSERT OR IGNORE INTO es_a_eo_propio (es_norm, eo) VALUES (?, ?)",
            (es, eo),
        )
        ok += 1

    con.commit()
    con.close()
    print(f"Pares cargados: {ok}")
    print(f"Descartados: {descartadas}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    importar(Path(sys.argv[1]), Path(sys.argv[2]))
