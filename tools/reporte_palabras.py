"""Genera informes de palabras no encontradas o sin traducir.

Crea la carpeta 'reportes' con tres archivos:
  1. no_encontradas.csv   Palabras que buscaste en el editor y no estaban en la base de datos
                          (ordenadas por número de búsquedas).
  2. raices_invalidas.txt Líneas de traducciones/*.csv cuyo esperanto no existe en el diccionario.
  3. sin_traduccion.txt   Palabras de esperanto del diccionario que todavía no tienen
                          ningún par castellano en es_a_eo_propio.

Uso (desde la carpeta del proyecto):
    python tools/reporte_palabras.py data/diccionario.db traducciones
"""
import csv
import sqlite3
import sys
from pathlib import Path


def informe_no_encontradas(con, salida: Path) -> int:
    try:
        filas = con.execute(
            "SELECT palabra, veces, ultima FROM no_encontradas ORDER BY veces DESC, palabra"
        ).fetchall()
    except sqlite3.OperationalError:
        filas = []  # la tabla aún no existe: nadie ha buscado nada no encontrado
    with salida.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["palabra", "veces", "ultima_busqueda"])
        w.writerows(filas)
    return len(filas)


def informe_raices_invalidas(con, carpeta: Path, salida: Path) -> int:
    existentes = {r[0] for r in con.execute("SELECT eo_norm FROM entradas")}
    malas = []
    for ruta in sorted(carpeta.glob("*.csv")):
        with ruta.open(encoding="utf-8") as f:
            for n, fila in enumerate(csv.reader(f, delimiter=";"), start=1):
                if len(fila) != 2:
                    malas.append(f"{ruta.name}:{n}  formato incorrecto  {fila}")
                    continue
                eo = fila[0].strip().lower()
                if eo not in existentes:
                    malas.append(f"{ruta.name}:{n}  no existe en el diccionario  {eo} ; {fila[1].strip()}")
    salida.write_text("\n".join(malas) + ("\n" if malas else ""), encoding="utf-8")
    return len(malas)


def informe_sin_traduccion(con, salida: Path) -> int:
    filas = con.execute(
        """SELECT e.eo_norm, e.categoria
           FROM entradas e
           WHERE NOT EXISTS (SELECT 1 FROM es_a_eo_propio p WHERE p.eo = e.eo_norm)
           GROUP BY e.eo_norm
           ORDER BY e.eo_norm"""
    ).fetchall()
    with salida.open("w", encoding="utf-8") as f:
        for eo, cat in filas:
            f.write(f"{eo}\t{cat or ''}\n")
    return len(filas)


def main(ruta_db: Path, carpeta_raices: Path) -> None:
    salida = Path("reportes")
    salida.mkdir(exist_ok=True)
    con = sqlite3.connect(ruta_db)

    n1 = informe_no_encontradas(con, salida / "no_encontradas.csv")
    n2 = informe_raices_invalidas(con, carpeta_raices, salida / "raices_invalidas.txt")
    n3 = informe_sin_traduccion(con, salida / "sin_traduccion.txt")
    con.close()

    print(f"No encontradas en el editor: {n1}  -> reportes\\no_encontradas.csv")
    print(f"Raíces inválidas en los CSV: {n2}  -> reportes\\raices_invalidas.txt")
    print(f"Palabras de esperanto sin traducción: {n3}  -> reportes\\sin_traduccion.txt")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
