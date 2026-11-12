"""Importa entradas de esperanto de un volcado JSONL de Wiktionary (formato kaikki.org / wiktextract)
a una base SQLite local que usará el editor.

Uso (desde la carpeta del proyecto):
    python tools/importar_wiktionary.py ruta/al/volcado.jsonl data/diccionario.db

Solo usa la biblioteca estándar de Python.
"""
import json
import sqlite3
import sys
from pathlib import Path

ESQUEMA = """
CREATE TABLE IF NOT EXISTS entradas (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    eo        TEXT NOT NULL,          -- palabra en esperanto
    eo_norm   TEXT NOT NULL,          -- minúsculas, para búsquedas
    categoria TEXT,                   -- sustantivo, verbo, etc.
    es        TEXT,                   -- traducciones al castellano, separadas por '; '
    en        TEXT,                   -- primera definición en inglés (referencia)
    fuente    TEXT DEFAULT 'wiktionary'
);
CREATE INDEX IF NOT EXISTS idx_eo_norm ON entradas(eo_norm);

CREATE TABLE IF NOT EXISTS es_a_eo (
    es_norm   TEXT NOT NULL,          -- castellano en minúsculas
    eo        TEXT NOT NULL,
    PRIMARY KEY (es_norm, eo)
);
CREATE INDEX IF NOT EXISTS idx_es_norm ON es_a_eo(es_norm);
"""


def extraer(entrada: dict):
    """Devuelve (eo, categoria, traducciones_es, primera_glosa_en) o None si no es esperanto."""
    if entrada.get("lang_code") != "eo":
        return None
    palabra = entrada.get("word", "").strip()
    if not palabra:
        return None

    # Traducciones al castellano: aparecen en el nivel superior de la entrada
    es = []
    for t in entrada.get("translations", []):
        if t.get("lang_code") == "es" and t.get("word"):
            if t["word"] not in es:
                es.append(t["word"])

    # Primera glosa en inglés como referencia
    en = None
    for sentido in entrada.get("senses", []):
        glosas = sentido.get("glosses") or []
        if glosas:
            en = glosas[0]
            break

    return palabra, entrada.get("pos"), es, en


def importar(ruta_jsonl: Path, ruta_db: Path) -> None:
    ruta_db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta_db)
    con.executescript(ESQUEMA)

    total = guardadas = con_es = 0
    with ruta_jsonl.open(encoding="utf-8") as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue
            total += 1
            try:
                datos = json.loads(linea)
            except json.JSONDecodeError:
                continue
            resultado = extraer(datos)
            if resultado is None:
                continue
            eo, cat, es_list, en = resultado
            es_txt = "; ".join(es_list) if es_list else None

            con.execute(
                "INSERT INTO entradas (eo, eo_norm, categoria, es, en) VALUES (?, ?, ?, ?, ?)",
                (eo, eo.lower(), cat, es_txt, en),
            )
            for palabra_es in es_list:
                con.execute(
                    "INSERT OR IGNORE INTO es_a_eo (es_norm, eo) VALUES (?, ?)",
                    (palabra_es.lower(), eo),
                )
            guardadas += 1
            if es_list:
                con_es += 1

    con.commit()
    con.close()
    print(f"Líneas leídas: {total}")
    print(f"Entradas de esperanto guardadas: {guardadas}")
    print(f"Con traducción al castellano: {con_es}")
    print(f"Base de datos: {ruta_db}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    importar(Path(sys.argv[1]), Path(sys.argv[2]))
