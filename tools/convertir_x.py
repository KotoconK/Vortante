"""Convierte el sistema x del diccionario (cx, gx, hx, jx, sx, ux) a letras con acento.

Ejemplo: mangxi → manĝi, cxu → ĉu.

- En es_a_eo_propio: las traducciones con sistema x pasan a la forma con acento.
- En entradas: las entradas con sistema x se copian a la forma con acento (si no existe ya)
  y se borra la entrada con x.

Uso (desde la carpeta del proyecto):
    python tools/convertir_x.py data/diccionario.db
"""
import re
import sqlite3
import sys
from pathlib import Path

PATRON_X = re.compile(r"[cghjsu]x")
CONVERSION = {"cx": "ĉ", "gx": "ĝ", "hx": "ĥ", "jx": "ĵ", "sx": "ŝ", "ux": "ŭ"}


def convertir(w: str) -> str:
    return re.sub(r"(cx|gx|hx|jx|sx|ux)", lambda m: CONVERSION[m.group(0)], w)


def hay_x(w: str) -> bool:
    return PATRON_X.search(w) is not None


def main(ruta_db: Path) -> None:
    con = sqlite3.connect(ruta_db)

    # 1) Traducciones
    pares = [r for r in con.execute(
        "SELECT es_norm, eo, fuente FROM es_a_eo_propio") if hay_x(r[1])]
    for es, eo, fuente in pares:
        con.execute("INSERT OR IGNORE INTO es_a_eo_propio (es_norm, eo, fuente) VALUES (?, ?, ?)",
                    (es, convertir(eo), fuente))
        con.execute("DELETE FROM es_a_eo_propio WHERE es_norm = ? AND eo = ?", (es, eo))

    # 2) Entradas del diccionario
    entradas = [r for r in con.execute(
        "SELECT id, eo, eo_norm, categoria, es, en, fuente FROM entradas") if hay_x(r[2])]
    copiadas = 0
    for id_, eo, eo_norm, categoria, es, en, fuente in entradas:
        nueva = convertir(eo_norm)
        existe = con.execute("SELECT 1 FROM entradas WHERE eo_norm = ? LIMIT 1",
                             (nueva,)).fetchone()
        if not existe:
            con.execute(
                "INSERT INTO entradas (eo, eo_norm, categoria, es, en, fuente) VALUES (?, ?, ?, ?, ?, ?)",
                (convertir(eo), nueva, categoria, es, en, fuente))
            copiadas += 1
        con.execute("DELETE FROM entradas WHERE id = ?", (id_,))

    con.commit()
    con.close()
    print(f"Traducciones convertidas: {len(pares)}")
    print(f"Entradas con sistema x eliminadas: {len(entradas)} (copiadas en su forma con acento: {copiadas})")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(Path(sys.argv[1]))
