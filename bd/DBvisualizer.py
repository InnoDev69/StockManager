import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk
import sqlite3
import re
import importlib.util
import os


module_path = os.path.join(os.path.dirname(__file__), '..', 'Opacity', 'py_win_style.py')
spec = importlib.util.spec_from_file_location("configstyle", module_path)
configstyle = importlib.util.module_from_spec(spec)

class BDViewerApp:
    MAX_ROWS_DISPLAY = 500 
    MAX_COLUMNS_DISPLAY = 50 

    def __init__(self, root):
        self.root = root
        self.root.title("BD Viewer")
        self.root.geometry("1000x600")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        
        self.conn = None
        self.sql_keywords = ["SELECT", "FROM", "WHERE", "INSERT INTO", "DELETE", "UPDATE", "JOIN", "ON", "ORDER BY", "GROUP BY"]
        self._create_interface()
        self.root.resizable(False, False)  
        self.current_suggestion = ""
        self.tables_and_columns = {}  # Cache para almacenar tablas y sus columnas
        #configstyle.apply_style(self.root, 'acrylic')

    def _create_interface(self):
        frame_top = ctk.CTkFrame(self.root)
        frame_top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(frame_top, text="Gestión de Archivo y Consultas").pack()

        self.btn_load = ctk.CTkButton(frame_top, text="Cargar Archivo .db", command=self.load_bd_file)
        self.btn_load.pack(side="left", padx=5, pady=5)

        self.lbl_filename = ctk.CTkLabel(frame_top, text="Archivo no cargado.")
        self.lbl_filename.pack(side="left", padx=10, pady=5)
        
        self.query_entry = ctk.CTkEntry(frame_top, width=300)
        self.query_entry.pack(side="left", padx=10, pady=5)
        self.query_entry.bind("<KeyRelease>", self.suggest_autocomplete)
        self.query_entry.bind("<Tab>", self.apply_suggestion)
        
        self.suggestion_label = ctk.CTkLabel(frame_top, text="", text_color="grey", font=("Arial", 10))
        self.suggestion_label.pack(side="left", padx=5)

        self.btn_query = ctk.CTkButton(frame_top, text="Ejecutar Consulta", command=self.run_query)
        self.btn_query.pack(side="left", padx=5, pady=5)

        frame_main = ctk.CTkFrame(self.root)
        frame_main.pack(fill="both", expand=True, padx=10, pady=10)

        frame_left = ctk.CTkFrame(frame_main)
        frame_left.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(frame_left, text="Tablas en la Base de Datos").pack()

        self.table_tree = ttk.Treeview(frame_left, show="tree", height=15)
        self.table_tree.pack(fill="y", expand=True)
        self.table_tree.bind("<<TreeviewSelect>>", self.display_table_content)
        
        frame_right = ctk.CTkFrame(frame_main)
        frame_right.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(frame_right, text="Contenido de la Tabla / Resultados de la Consulta").pack()

        self.content_tree = ttk.Treeview(frame_right, show="headings", height=20)
        self.content_tree.pack(side="left", fill="both", expand=True)

        # Configurar scrollbars para el Treeview de contenido
        vsb = ttk.Scrollbar(frame_right, orient="vertical", command=self.content_tree.yview)
        vsb.pack(side="right", fill="y")
        hsb = ttk.Scrollbar(frame_right, orient="horizontal", command=self.content_tree.xview)
        hsb.pack(side="bottom", fill="x")
        self.content_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        # Aplicar estilo a los Treeviews
        self.style = ttk.Style()
        self.style.theme_use("clam")  # Usar un tema compatible con modo oscuro
        self.style.configure("Treeview", 
                             background="#2a2d2e", 
                             foreground="white", 
                             rowheight=25, 
                             fieldbackground="#2a2d2e")
        self.style.map('Treeview', background=[('selected', '#22559b')])
        
        self.style.configure("Treeview.Heading",
                             background="#565b5e",
                             foreground="white",
                             relief="flat")
        self.style.map("Treeview.Heading",
                       background=[('active', '#3484F0')])

    def load_bd_file(self):
        if file_path := filedialog.askopenfilename(
            filetypes=[("SQLite Database Files", "*.db")]
        ):
            self.lbl_filename.configure(text=file_path)
            self.connect_to_db(file_path)

    def connect_to_db(self, file_path):
        try:
            if self.conn:
                self.conn.close()
            self.conn = sqlite3.connect(file_path)
            self.cache_tables_and_columns()
            self.show_tables()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"No se pudo conectar a la base de datos: {e}")

    def cache_tables_and_columns(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        self.tables_and_columns = {}
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = [col[1] for col in cursor.fetchall()]
            self.tables_and_columns[table_name] = columns
        cursor.close()

    def show_tables(self):
        for item in self.table_tree.get_children():
            self.table_tree.delete(item)
        for table in self.tables_and_columns:
            self.table_tree.insert("", "end", text=table, values=(table,))

    def display_table_content(self, event):
        if selected_items := self.table_tree.selection():
            selected_table = self.table_tree.item(selected_items[0])['text']
            self._display_table_data(selected_table)

    def _display_table_data(self, table_name):
        self._clear_content_tree()
        cursor = self.conn.cursor()
        columns = self.tables_and_columns.get(table_name, [])
        cursor.execute(f"SELECT * FROM {table_name} LIMIT {self.MAX_ROWS_DISPLAY};")
        rows = cursor.fetchall()
        
        self.content_tree["columns"] = columns
        for col in columns:
            self.content_tree.heading(col, text=col, anchor="w")
            self.content_tree.column(col, anchor="w", width=100)  # Ajustar el ancho según sea necesario
        
        for row in rows:
            self.content_tree.insert("", "end", values=row)
        
        cursor.close()

    def run_query(self):
        query = self.query_entry.get().strip()
        if not query:
            messagebox.showwarning("Warning", "Por favor, ingrese una consulta.")
            return
        try:
            cursor = self.conn.cursor()
            cursor.execute(query)
            if query.lower().startswith("select"):
                results = cursor.fetchmany(self.MAX_ROWS_DISPLAY)
                self._show_query_results(results, cursor.description)
            else:
                self.conn.commit()
                messagebox.showinfo("Info", "Consulta ejecutada con éxito.")
                self.show_tables()
            cursor.close()
        except sqlite3.Error as e:
            messagebox.showerror("Error", f"Error en la ejecución de la consulta: {e}")

    def _show_query_results(self, results, description):
        self._clear_content_tree()
        if results:
            columns = [desc[0] for desc in description]
            self.content_tree["columns"] = columns
            for col in columns:
                self.content_tree.heading(col, text=col, anchor="w")
                self.content_tree.column(col, anchor="w", width=100)  # Ajustar el ancho según sea necesario
            
            for row in results:
                self.content_tree.insert("", "end", values=row)

    def _clear_content_tree(self):
        for item in self.content_tree.get_children():
            self.content_tree.delete(item)

    def suggest_autocomplete(self, event):
        current_text = self.query_entry.get().strip().upper()
        if suggestions := self._generate_suggestions(current_text):
            self.current_suggestion = suggestions[0]
            self.suggestion_label.configure(text=self.current_suggestion)
        else:
            self.suggestion_label.configure(text="")

    def apply_suggestion(self, event):
        self.query_entry.delete(0, "end")
        self.query_entry.insert(0, self.current_suggestion)
        self.suggestion_label.configure(text="")
        return "break"

    def _generate_suggestions(self, current_text):
        suggestions = []
        last_keyword = self.get_last_keyword(current_text)

        if last_keyword == "SELECT":
            for table, columns in self.tables_and_columns.items():
                suggestions.extend(columns)
        elif last_keyword == "FROM":
            suggestions.extend(self.tables_and_columns.keys())
        else:
            suggestions.extend([kw for kw in self.sql_keywords if kw.startswith(current_text)])
        
        return suggestions

    def get_last_keyword(self, current_text):
        words = re.split(r"\s+", current_text)
        return next(
            (word for word in reversed(words) if word in self.sql_keywords), ""
        )

    def on_closing(self):
        if self.conn:
            self.conn.close()
        self.root.destroy()

if __name__ == "__main__":
    root = ctk.CTk()
    app = BDViewerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()