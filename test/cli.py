import cmd
import code
import pdb
import shlex
import sqlite3
import time
import traceback
from pprint import pprint

from bd.bdInstance import db
from bd.bdConector import BDConector
from bd.bdErrors import DatabaseError, StockError


def _print_table(headers, rows, max_width=40):
    if not rows:
        print("(sin resultados)")
        return

    widths = [len(str(h)) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            txt = str(cell)
            if len(txt) > max_width:
                txt = txt[: max_width - 3] + "..."
            widths[i] = max(widths[i], len(txt))

    sep = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    print(sep)
    print("| " + " | ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers)) + " |")
    print(sep)
    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            txt = str(cell)
            if len(txt) > max_width:
                txt = txt[: max_width - 3] + "..."
            cells.append(txt.ljust(widths[i]))
        print("| " + " | ".join(cells) + " |")
    print(sep)


class StockManagerCLI(cmd.Cmd):
    intro = (
        "\nStockManager CLI Debug\n"
        "Escribe 'help' para ver comandos.\n"
    )
    prompt = "stock> "

    def __init__(self):
        super().__init__()
        self.ctx = {
            "db": db,
            "BDConector": BDConector,
            "DatabaseError": DatabaseError,
            "StockError": StockError,
            "pprint": pprint,
        }

    # ---------------------------
    # Comandos base
    # ---------------------------
    def do_info(self, arg):
        """Muestra informacion del entorno y DB."""
        print(f"DB path: {db.db_path}")
        print("Contexto disponible:", ", ".join(sorted(self.ctx.keys())))

    def do_methods(self, arg):
        """Lista metodos publicos de db. Uso: methods [filtro]"""
        filt = (arg or "").strip().lower()
        names = [m for m in dir(db) if not m.startswith("_")]
        if filt:
            names = [m for m in names if filt in m.lower()]
        for n in sorted(names):
            print(n)

    def do_exit(self, arg):
        """Salir."""
        return True

    def do_quit(self, arg):
        """Salir."""
        return True

    # ---------------------------
    # Python dinamico
    # ---------------------------
    def do_py(self, arg):
        """Eval/exec de una linea Python. Ej: py db.total_items()"""
        src = arg.strip()
        if not src:
            print("Uso: py <expresion o sentencia>")
            return
        try:
            try:
                result = eval(src, {}, self.ctx)
                if result is not None:
                    pprint(result)
            except SyntaxError:
                exec(src, {}, self.ctx)
        except Exception:
            traceback.print_exc()

    def do_block(self, arg):
        """
        Ejecuta un bloque Python multilinea.
        Termina con una linea que contenga solo: EOF
        """
        print("Ingresa bloque Python. Finaliza con EOF")
        lines = []
        while True:
            line = input("... ")
            if line.strip() == "EOF":
                break
            lines.append(line)
        src = "\n".join(lines)
        try:
            exec(src, {}, self.ctx)
        except Exception:
            traceback.print_exc()

    def do_repl(self, arg):
        """Abre un mini-REPL Python con el contexto del proyecto."""
        banner = (
            "REPL local. Contexto: db, BDConector, DatabaseError, StockError, pprint\n"
            "Salir con Ctrl-D.\n"
        )
        code.InteractiveConsole(self.ctx).interact(banner=banner)

    def do_debug(self, arg):
        """
        Ejecuta codigo bajo pdb.
        Uso:
          debug py db.total_items()
          debug block   (multilinea, termina con EOF)
        """
        mode = (arg or "").strip()
        if mode.startswith("py "):
            src = mode[3:]
            try:
                pdb.run(src, globals={}, locals=self.ctx)
            except Exception:
                traceback.print_exc()
            return

        if mode == "block":
            print("Ingresa bloque Python para pdb. Finaliza con EOF")
            lines = []
            while True:
                line = input("... ")
                if line.strip() == "EOF":
                    break
                lines.append(line)
            src = "\n".join(lines)
            try:
                pdb.run(src, globals={}, locals=self.ctx)
            except Exception:
                traceback.print_exc()
            return

        print("Uso: debug py <codigo> | debug block")

    # ---------------------------
    # SQL / DB inspection
    # ---------------------------
    def do_tables(self, arg):
        """Lista tablas SQLite."""
        rows = db.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )
        names = [r[0] for r in rows]
        for n in names:
            print(n)

    def do_schema(self, arg):
        """Muestra schema de una tabla. Uso: schema <tabla>"""
        table = arg.strip()
        if not table:
            print("Uso: schema <tabla>")
            return
        rows = db.execute_query(f"PRAGMA table_info({table})")
        _print_table(["cid", "name", "type", "notnull", "dflt_value", "pk"], rows)

    def do_sql(self, arg):
        """Ejecuta SQL directo. Ej: sql SELECT * FROM items LIMIT 5"""
        q = arg.strip()
        if not q:
            print("Uso: sql <query>")
            return
        try:
            is_select = q.lower().lstrip().startswith(("select", "pragma", "with"))
            out = db.execute_query(q, fetch=is_select)
            if is_select:
                if out:
                    headers = [f"col_{i}" for i in range(len(out[0]))]
                    _print_table(headers, out)
                else:
                    print("(sin resultados)")
            else:
                print(f"OK. Filas afectadas: {out}")
        except Exception:
            traceback.print_exc()

    def do_show(self, arg):
        """Muestra filas de tabla. Uso: show <tabla> [limit]"""
        parts = shlex.split(arg)
        if not parts:
            print("Uso: show <tabla> [limit]")
            return
        table = parts[0]
        limit = int(parts[1]) if len(parts) > 1 else 20
        try:
            rows = db.execute_query(f"SELECT * FROM {table} LIMIT ?", (limit,))
            if not rows:
                print("(sin filas)")
                return

            with sqlite3.connect(db.db_path) as conn:
                cur = conn.cursor()
                cur.execute(f"PRAGMA table_info({table})")
                cols = [r[1] for r in cur.fetchall()]

            _print_table(cols, rows)
        except Exception:
            traceback.print_exc()

    def do_watch(self, arg):
        """
        Vigila cambios de una tabla por polling.
        Uso: watch <tabla> [intervalo_seg=1] [limit=10]
        Ctrl-C para detener.
        """
        parts = shlex.split(arg)
        if not parts:
            print("Uso: watch <tabla> [intervalo] [limit]")
            return

        table = parts[0]
        interval = float(parts[1]) if len(parts) > 1 else 1.0
        limit = int(parts[2]) if len(parts) > 2 else 10

        last = None
        print(f"Vigilando '{table}' cada {interval}s (limit {limit}). Ctrl-C para salir.")
        try:
            while True:
                try:
                    rows = db.execute_query(f"SELECT * FROM {table} ORDER BY 1 DESC LIMIT ?", (limit,))
                except Exception:
                    rows = db.execute_query(f"SELECT * FROM {table} LIMIT ?", (limit,))

                if rows != last:
                    print("\n--- cambio detectado ---", time.strftime("%H:%M:%S"))
                    if rows:
                        with sqlite3.connect(db.db_path) as conn:
                            cur = conn.cursor()
                            cur.execute(f"PRAGMA table_info({table})")
                            cols = [r[1] for r in cur.fetchall()]
                        _print_table(cols, rows)
                    else:
                        print("(tabla vacia)")
                    last = rows
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nwatch detenido.")

    def emptyline(self):
        pass


if __name__ == "__main__":
    StockManagerCLI().cmdloop()