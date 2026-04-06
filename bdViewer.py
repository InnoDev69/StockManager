"""
SQLite Viewer — Dark Mode
Requires: pip install customtkinter
Run:      python sqlite_viewer.py
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sqlite3
import os
import csv
import io
from datetime import datetime

# ─── Theme ────────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

COLORS = {
    "bg_deep":      "#0D0F14",
    "bg_panel":     "#13161E",
    "bg_card":      "#1A1D27",
    "bg_hover":     "#21253A",
    "bg_selected":  "#1E3A5F",
    "accent":       "#3B82F6",
    "accent_dim":   "#1D4ED8",
    "accent_glow":  "#60A5FA",
    "success":      "#22C55E",
    "warning":      "#F59E0B",
    "danger":       "#EF4444",
    "text_primary": "#E2E8F0",
    "text_muted":   "#64748B",
    "text_dim":     "#94A3B8",
    "border":       "#1E2438",
    "border_bright":"#2D3555",
    "mono_font":    ("JetBrains Mono", "Cascadia Code", "Consolas", "Courier New"),
}

MONO = COLORS["mono_font"]


# ─── Treeview Style ───────────────────────────────────────────────────────────
def apply_treeview_style():
    style = ttk.Style()
    style.theme_use("clam")

    style.configure(
        "Dark.Treeview",
        background=COLORS["bg_card"],
        foreground=COLORS["text_primary"],
        fieldbackground=COLORS["bg_card"],
        bordercolor=COLORS["border"],
        relief="flat",
        rowheight=28,
        font=(MONO[2], 11),
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=COLORS["bg_panel"],
        foreground=COLORS["accent_glow"],
        relief="flat",
        font=(MONO[2], 11, "bold"),
        bordercolor=COLORS["border"],
        padding=(8, 6),
    )
    style.map(
        "Dark.Treeview",
        background=[("selected", COLORS["bg_selected"])],
        foreground=[("selected", "#FFFFFF")],
    )
    style.map(
        "Dark.Treeview.Heading",
        background=[("active", COLORS["bg_hover"])],
    )
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=COLORS["bg_panel"],
        troughcolor=COLORS["bg_deep"],
        bordercolor=COLORS["border"],
        arrowcolor=COLORS["text_muted"],
        relief="flat",
    )
    style.configure(
        "Dark.Horizontal.TScrollbar",
        background=COLORS["bg_panel"],
        troughcolor=COLORS["bg_deep"],
        bordercolor=COLORS["border"],
        arrowcolor=COLORS["text_muted"],
        relief="flat",
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────
def truncate(val, n=80):
    s = str(val)
    return s[:n] + "…" if len(s) > n else s


def fmt_num(n):
    return f"{n:,}"


# ─── Main Application ─────────────────────────────────────────────────────────
class SQLiteViewer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SQLite Viewer")
        self.geometry("1280x820")
        self.minsize(900, 600)
        self.configure(fg_color=COLORS["bg_deep"])

        apply_treeview_style()

        self.conn: sqlite3.Connection | None = None
        self.db_path: str = ""
        self.current_table: str = ""
        self.sort_col: str = ""
        self.sort_asc: bool = True
        self.current_page: int = 0
        self.page_size: int = 500
        self.total_rows: int = 0
        self.all_columns: list = []
        self.query_history: list = []

        self._build_ui()
        self._bind_shortcuts()

    # ── UI Construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # Top bar
        self._build_topbar()

        # Body: sidebar + main
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=0, pady=0)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        self._build_sidebar(body)
        self._build_main(body)

        # Status bar
        self._build_statusbar()

    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], height=56,
                           corner_radius=0)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Logo / title
        ctk.CTkLabel(
            bar, text="⬡  SQLite Viewer",
            font=ctk.CTkFont(family=MONO[2], size=16, weight="bold"),
            text_color=COLORS["accent_glow"],
        ).pack(side="left", padx=20, pady=10)

        # Buttons (right-aligned)
        btn_cfg = dict(
            height=34, corner_radius=6,
            font=ctk.CTkFont(family=MONO[2], size=12),
        )

        ctk.CTkButton(
            bar, text="⊞  Export CSV", width=120,
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            border_width=1, border_color=COLORS["border_bright"],
            text_color=COLORS["text_dim"],
            command=self._export_csv, **btn_cfg,
        ).pack(side="right", padx=(0, 16), pady=11)

        ctk.CTkButton(
            bar, text="↺  Refresh", width=100,
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            border_width=1, border_color=COLORS["border_bright"],
            text_color=COLORS["text_dim"],
            command=self._refresh, **btn_cfg,
        ).pack(side="right", padx=(0, 8), pady=11)

        ctk.CTkButton(
            bar, text="◉  Open DB", width=110,
            fg_color=COLORS["accent_dim"], hover_color=COLORS["accent"],
            text_color="#FFFFFF",
            command=self._open_db, **btn_cfg,
        ).pack(side="right", padx=(0, 8), pady=11)

        # DB path label
        self.db_label = ctk.CTkLabel(
            bar, text="No database loaded",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["text_muted"],
        )
        self.db_label.pack(side="left", padx=8, pady=10)

    def _build_sidebar(self, parent):
        sidebar = ctk.CTkFrame(
            parent, width=220, fg_color=COLORS["bg_panel"],
            corner_radius=0,
        )
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.rowconfigure(2, weight=1)

        # Section header
        ctk.CTkLabel(
            sidebar, text="TABLES",
            font=ctk.CTkFont(family=MONO[2], size=10, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(16, 4))

        # Search tables
        self.table_search = ctk.CTkEntry(
            sidebar, placeholder_text="Filter tables…",
            font=ctk.CTkFont(family=MONO[2], size=11),
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border_bright"],
            text_color=COLORS["text_primary"],
            height=32, corner_radius=6,
        )
        self.table_search.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 6))
        self.table_search.bind("<KeyRelease>", self._filter_tables)
        sidebar.columnconfigure(0, weight=1)

        # Table list
        list_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent",
            scrollbar_button_color=COLORS["border_bright"],
        )
        list_frame.grid(row=2, column=0, sticky="nsew", padx=4)
        self.table_list_frame = list_frame

        # Stats
        self.sidebar_stats = ctk.CTkLabel(
            sidebar, text="",
            font=ctk.CTkFont(family=MONO[2], size=10),
            text_color=COLORS["text_muted"],
        )
        self.sidebar_stats.grid(row=3, column=0, sticky="w", padx=14, pady=(4, 12))

    def _build_main(self, parent):
        main = ctk.CTkFrame(parent, fg_color="transparent")
        main.grid(row=0, column=1, sticky="nsew", padx=0)
        main.rowconfigure(1, weight=1)
        main.columnconfigure(0, weight=1)

        # ── Tabs ──────────────────────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(
            main,
            fg_color=COLORS["bg_card"],
            segmented_button_fg_color=COLORS["bg_panel"],
            segmented_button_selected_color=COLORS["accent_dim"],
            segmented_button_selected_hover_color=COLORS["accent"],
            segmented_button_unselected_color=COLORS["bg_panel"],
            segmented_button_unselected_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_primary"],
            corner_radius=0,
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", rowspan=2)

        self.tabview.add("  Data  ")
        self.tabview.add("  Query  ")
        self.tabview.add("  Schema  ")
        self.tabview.add("  Info  ")

        self._build_data_tab(self.tabview.tab("  Data  "))
        self._build_query_tab(self.tabview.tab("  Query  "))
        self._build_schema_tab(self.tabview.tab("  Schema  "))
        self._build_info_tab(self.tabview.tab("  Info  "))

    def _build_data_tab(self, tab):
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        # Toolbar
        tb = ctk.CTkFrame(tab, fg_color="transparent", height=44)
        tb.grid(row=0, column=0, sticky="ew", padx=10, pady=(6, 0))

        self.table_title = ctk.CTkLabel(
            tb, text="Select a table →",
            font=ctk.CTkFont(family=MONO[2], size=13, weight="bold"),
            text_color=COLORS["accent_glow"],
        )
        self.table_title.pack(side="left", padx=4)

        self.row_count_label = ctk.CTkLabel(
            tb, text="",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["text_muted"],
        )
        self.row_count_label.pack(side="left", padx=8)

        # Search
        self.data_search = ctk.CTkEntry(
            tb, placeholder_text="⌕  Search visible rows…",
            font=ctk.CTkFont(family=MONO[2], size=11),
            fg_color=COLORS["bg_panel"],
            border_color=COLORS["border_bright"],
            text_color=COLORS["text_primary"],
            height=30, width=220, corner_radius=6,
        )
        self.data_search.pack(side="right", padx=4)
        self.data_search.bind("<KeyRelease>", self._search_rows)

        # Page nav
        self.next_btn = ctk.CTkButton(
            tb, text="▶", width=30, height=30,
            fg_color=COLORS["bg_panel"], hover_color=COLORS["bg_hover"],
            border_width=1, border_color=COLORS["border_bright"],
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(family=MONO[2], size=12),
            command=self._next_page,
        )
        self.next_btn.pack(side="right", padx=2)

        self.page_label = ctk.CTkLabel(
            tb, text="",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["text_muted"],
        )
        self.page_label.pack(side="right", padx=4)

        self.prev_btn = ctk.CTkButton(
            tb, text="◀", width=30, height=30,
            fg_color=COLORS["bg_panel"], hover_color=COLORS["bg_hover"],
            border_width=1, border_color=COLORS["border_bright"],
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(family=MONO[2], size=12),
            command=self._prev_page,
        )
        self.prev_btn.pack(side="right", padx=2)

        # Treeview
        tree_frame = tk.Frame(tab, bg=COLORS["bg_deep"])
        tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            tree_frame, style="Dark.Treeview", show="headings", selectmode="extended",
        )
        vsb = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview,
            style="Dark.Vertical.TScrollbar",
        )
        hsb = ttk.Scrollbar(
            tree_frame, orient="horizontal", command=self.tree.xview,
            style="Dark.Horizontal.TScrollbar",
        )
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        # Alternating row colors
        self.tree.tag_configure("odd",  background=COLORS["bg_card"])
        self.tree.tag_configure("even", background="#161924")
        self.tree.tag_configure("null", foreground=COLORS["text_muted"])

        self.tree.bind("<Button-1>", self._on_tree_click)

    def _build_query_tab(self, tab):
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)

        # Editor area
        edit_frame = ctk.CTkFrame(tab, fg_color=COLORS["bg_panel"],
                                  corner_radius=8)
        edit_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        edit_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(
            edit_frame, text="SQL EDITOR",
            font=ctk.CTkFont(family=MONO[2], size=10, weight="bold"),
            text_color=COLORS["text_muted"],
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(8, 0))

        self.sql_editor = ctk.CTkTextbox(
            edit_frame, height=130,
            font=ctk.CTkFont(family=MONO[2], size=12),
            fg_color=COLORS["bg_deep"],
            text_color=COLORS["text_primary"],
            border_color=COLORS["border_bright"],
            border_width=1,
            corner_radius=6,
            wrap="none",
        )
        self.sql_editor.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        self.sql_editor.insert("1.0", "SELECT * FROM sqlite_master WHERE type='table';")

        btn_row = ctk.CTkFrame(edit_frame, fg_color="transparent")
        btn_row.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        ctk.CTkButton(
            btn_row, text="▶  Run Query  (Ctrl+Enter)", width=180, height=34,
            fg_color=COLORS["accent_dim"], hover_color=COLORS["accent"],
            text_color="#FFFFFF",
            font=ctk.CTkFont(family=MONO[2], size=12),
            command=self._run_query,
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="✕  Clear", width=80, height=34,
            fg_color=COLORS["bg_card"], hover_color=COLORS["bg_hover"],
            border_width=1, border_color=COLORS["border_bright"],
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(family=MONO[2], size=12),
            command=lambda: (self.sql_editor.delete("1.0", "end"),),
        ).pack(side="left", padx=8)

        self.query_time_label = ctk.CTkLabel(
            btn_row, text="",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["success"],
        )
        self.query_time_label.pack(side="left", padx=8)

        # History dropdown
        self.history_var = ctk.StringVar(value="History")
        self.history_menu = ctk.CTkOptionMenu(
            btn_row, variable=self.history_var,
            values=["No history yet"],
            fg_color=COLORS["bg_card"],
            button_color=COLORS["border_bright"],
            button_hover_color=COLORS["bg_hover"],
            text_color=COLORS["text_dim"],
            font=ctk.CTkFont(family=MONO[2], size=11),
            width=180, height=34, corner_radius=6,
            command=self._load_history,
        )
        self.history_menu.pack(side="right")

        # Results treeview
        results_outer = tk.Frame(tab, bg=COLORS["bg_deep"])
        results_outer.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        results_outer.rowconfigure(0, weight=1)
        results_outer.columnconfigure(0, weight=1)

        self.query_tree = ttk.Treeview(
            results_outer, style="Dark.Treeview", show="headings",
        )
        vsb2 = ttk.Scrollbar(
            results_outer, orient="vertical", command=self.query_tree.yview,
            style="Dark.Vertical.TScrollbar",
        )
        hsb2 = ttk.Scrollbar(
            results_outer, orient="horizontal", command=self.query_tree.xview,
            style="Dark.Horizontal.TScrollbar",
        )
        self.query_tree.configure(yscrollcommand=vsb2.set, xscrollcommand=hsb2.set)
        self.query_tree.grid(row=0, column=0, sticky="nsew")
        vsb2.grid(row=0, column=1, sticky="ns")
        hsb2.grid(row=1, column=0, sticky="ew")
        self.query_tree.tag_configure("odd",  background=COLORS["bg_card"])
        self.query_tree.tag_configure("even", background="#161924")

        # Error label
        self.query_error = ctk.CTkLabel(
            tab, text="",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["danger"],
            wraplength=700,
        )
        self.query_error.grid(row=2, column=0, sticky="w", padx=14, pady=(0, 4))

    def _build_schema_tab(self, tab):
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)

        frame = tk.Frame(tab, bg=COLORS["bg_deep"])
        frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        self.schema_tree = ttk.Treeview(
            frame,
            style="Dark.Treeview",
            columns=("cid", "name", "type", "notnull", "default", "pk"),
            show="headings",
        )
        for col, label, width in [
            ("cid",     "#",       40),
            ("name",    "Column",  180),
            ("type",    "Type",    120),
            ("notnull", "NOT NULL", 80),
            ("default", "Default", 120),
            ("pk",      "PK",       40),
        ]:
            self.schema_tree.heading(col, text=label)
            self.schema_tree.column(col, width=width, anchor="w")

        vsb = ttk.Scrollbar(frame, orient="vertical",
                            command=self.schema_tree.yview,
                            style="Dark.Vertical.TScrollbar")
        self.schema_tree.configure(yscrollcommand=vsb.set)
        self.schema_tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        self.schema_tree.tag_configure("pk_col", foreground=COLORS["accent_glow"])

    def _build_info_tab(self, tab):
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)

        outer = ctk.CTkScrollableFrame(
            tab, fg_color="transparent",
            scrollbar_button_color=COLORS["border_bright"],
        )
        outer.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        outer.columnconfigure(0, weight=1)

        self.info_inner = outer

    # ── Status bar ────────────────────────────────────────────────────────────
    def _build_statusbar(self):
        sb = ctk.CTkFrame(self, fg_color=COLORS["bg_panel"], height=28,
                          corner_radius=0)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            sb, text="Ready — open a SQLite database to begin",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["text_muted"],
        )
        self.status_label.pack(side="left", padx=14)

        self.status_right = ctk.CTkLabel(
            sb, text="",
            font=ctk.CTkFont(family=MONO[2], size=11),
            text_color=COLORS["text_muted"],
        )
        self.status_right.pack(side="right", padx=14)

    def _set_status(self, msg, right=""):
        self.status_label.configure(text=msg)
        self.status_right.configure(text=right)

    # ── Keyboard Shortcuts ────────────────────────────────────────────────────
    def _bind_shortcuts(self):
        self.bind("<Control-o>", lambda e: self._open_db())
        self.bind("<Control-r>", lambda e: self._refresh())
        self.bind("<Control-Return>", lambda e: self._run_query())
        self.sql_editor.bind("<Control-Return>", lambda e: self._run_query())

    # ── Database Operations ───────────────────────────────────────────────────
    def _open_db(self):
        path = filedialog.askopenfilename(
            title="Open SQLite Database",
            filetypes=[("SQLite files", "*.db *.sqlite *.sqlite3 *.s3db"),
                       ("All files", "*.*")],
        )
        if not path:
            return
        try:
            if self.conn:
                self.conn.close()
            self.conn = sqlite3.connect(path)
            self.db_path = path
            name = os.path.basename(path)
            self.db_label.configure(text=f"  {name}  ({path})")
            self.title(f"SQLite Viewer — {name}")
            self._load_tables()
            self._load_db_info()
            self._set_status(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"Cannot open database:\n{e}")

    def _refresh(self):
        if not self.conn:
            return
        self._load_tables()
        if self.current_table:
            self._show_table(self.current_table)

    def _load_tables(self):
        if not self.conn:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        self.all_tables = [r[0] for r in cur.fetchall()]
        self._render_table_list(self.all_tables)
        self.sidebar_stats.configure(
            text=f"{len(self.all_tables)} table(s)"
        )

    def _render_table_list(self, tables):
        for w in self.table_list_frame.winfo_children():
            w.destroy()

        for name in tables:
            btn = ctk.CTkButton(
                self.table_list_frame,
                text=f"◈  {name}",
                anchor="w",
                font=ctk.CTkFont(family=MONO[2], size=11),
                fg_color="transparent",
                hover_color=COLORS["bg_hover"],
                text_color=COLORS["text_dim"],
                height=30, corner_radius=4,
                command=lambda n=name: self._select_table(n),
            )
            btn.pack(fill="x", pady=1, padx=4)
            self._table_buttons = getattr(self, "_table_buttons", {})
            self._table_buttons[name] = btn

    def _filter_tables(self, event=None):
        q = self.table_search.get().lower()
        filtered = [t for t in getattr(self, "all_tables", []) if q in t.lower()]
        self._render_table_list(filtered)

    def _select_table(self, name):
        self.current_table = name
        self.current_page = 0
        self._show_table(name)
        self._show_schema(name)
        # Highlight
        for n, btn in getattr(self, "_table_buttons", {}).items():
            btn.configure(
                fg_color=COLORS["bg_selected"] if n == name else "transparent",
                text_color=COLORS["accent_glow"] if n == name else COLORS["text_dim"],
            )

    def _show_table(self, name):
        if not self.conn:
            return
        try:
            cur = self.conn.cursor()
            # Row count
            cur.execute(f'SELECT COUNT(*) FROM "{name}"')
            self.total_rows = cur.fetchone()[0]

            # Columns
            cur.execute(f'SELECT * FROM "{name}" LIMIT 0')
            self.all_columns = [d[0] for d in cur.description]

            # Fetch page
            offset = self.current_page * self.page_size
            order = ""
            if self.sort_col and self.sort_col in self.all_columns:
                direction = "ASC" if self.sort_asc else "DESC"
                order = f'ORDER BY "{self.sort_col}" {direction}'
            cur.execute(
                f'SELECT * FROM "{name}" {order} LIMIT {self.page_size} OFFSET {offset}'
            )
            rows = cur.fetchall()

            self._populate_tree(self.tree, self.all_columns, rows)

            total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
            self.table_title.configure(text=f"◈  {name}")
            self.row_count_label.configure(
                text=f"  {fmt_num(self.total_rows)} rows"
            )
            self.page_label.configure(
                text=f"Page {self.current_page + 1} / {total_pages}"
            )
            self._set_status(
                f"Table: {name}  •  {fmt_num(self.total_rows)} rows  •  "
                f"{len(self.all_columns)} columns",
                f"Page {self.current_page + 1}/{total_pages}",
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _populate_tree(self, tree, columns, rows):
        tree.delete(*tree.get_children())
        tree["columns"] = columns
        for col in columns:
            tree.heading(col, text=col,
                         command=lambda c=col: self._sort_by(c))
            tree.column(col, width=max(120, len(col) * 9), anchor="w",
                        minwidth=60)
        for i, row in enumerate(rows):
            tag = "odd" if i % 2 == 0 else "even"
            vals = [truncate(v) if v is not None else "NULL" for v in row]
            has_null = any(v is None for v in row)
            tags = (tag, "null") if has_null else (tag,)
            tree.insert("", "end", values=vals, tags=tags)

    def _show_schema(self, name):
        if not self.conn:
            return
        cur = self.conn.cursor()
        cur.execute(f'PRAGMA table_info("{name}")')
        rows = cur.fetchall()
        self.schema_tree.delete(*self.schema_tree.get_children())
        for row in rows:
            cid, col_name, col_type, notnull, default, pk = row
            tag = "pk_col" if pk else ""
            self.schema_tree.insert(
                "", "end",
                values=(cid, col_name, col_type or "—",
                        "✓" if notnull else "", default or "", "✓" if pk else ""),
                tags=(tag,),
            )

    def _load_db_info(self):
        if not self.conn:
            return
        for w in self.info_inner.winfo_children():
            w.destroy()

        cur = self.conn.cursor()
        info_items = []

        # File info
        size = os.path.getsize(self.db_path)
        info_items.append(("File", os.path.basename(self.db_path)))
        info_items.append(("Path", self.db_path))
        info_items.append(("File Size", f"{size:,} bytes  ({size/1024:.1f} KB)"))
        info_items.append(("Modified",
                           datetime.fromtimestamp(os.path.getmtime(self.db_path))
                           .strftime("%Y-%m-%d %H:%M:%S")))

        # PRAGMA info
        for pragma in ["page_size", "page_count", "journal_mode", "wal_autocheckpoint",
                       "synchronous", "encoding", "user_version", "application_id"]:
            try:
                cur.execute(f"PRAGMA {pragma}")
                val = cur.fetchone()
                if val:
                    info_items.append((pragma.replace("_", " ").title(), str(val[0])))
            except Exception:
                pass

        # Tables summary
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cur.fetchall()]
        info_items.append(("Tables", str(len(tables))))

        cur.execute("SELECT name FROM sqlite_master WHERE type='view'")
        views = cur.fetchall()
        info_items.append(("Views", str(len(views))))

        cur.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = cur.fetchall()
        info_items.append(("Indexes", str(len(indexes))))

        # Table sizes
        info_items.append(("─" * 20, ""))
        info_items.append(("TABLE ROW COUNTS", ""))
        for t in tables:
            try:
                cur.execute(f'SELECT COUNT(*) FROM "{t}"')
                cnt = cur.fetchone()[0]
                info_items.append((f"  {t}", fmt_num(cnt)))
            except Exception:
                pass

        # Render
        for i, (key, val) in enumerate(info_items):
            row_frame = ctk.CTkFrame(
                self.info_inner,
                fg_color=COLORS["bg_card"] if i % 2 == 0 else "transparent",
                corner_radius=4,
            )
            row_frame.grid(row=i, column=0, sticky="ew", pady=1, padx=4)
            row_frame.columnconfigure(1, weight=1)

            ctk.CTkLabel(
                row_frame, text=key,
                font=ctk.CTkFont(family=MONO[2], size=11, weight="bold"),
                text_color=COLORS["text_muted"],
                width=200, anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=10, pady=4)

            ctk.CTkLabel(
                row_frame, text=val,
                font=ctk.CTkFont(family=MONO[2], size=11),
                text_color=COLORS["text_primary"],
                anchor="w",
            ).grid(row=0, column=1, sticky="w", padx=8, pady=4)

        self.info_inner.columnconfigure(0, weight=1)

    # ── Query Execution ───────────────────────────────────────────────────────
    def _run_query(self):
        if not self.conn:
            messagebox.showwarning("No Database", "Open a database first.")
            return
        sql = self.sql_editor.get("1.0", "end").strip()
        if not sql:
            return
        self.query_error.configure(text="")
        t0 = datetime.now()
        try:
            cur = self.conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            elapsed = (datetime.now() - t0).total_seconds()
            if cur.description:
                cols = [d[0] for d in cur.description]
                self._populate_tree(self.query_tree, cols, rows)
                self.query_time_label.configure(
                    text=f"✓  {len(rows)} rows  •  {elapsed:.3f}s",
                    text_color=COLORS["success"],
                )
            else:
                self.conn.commit()
                self.query_tree.delete(*self.query_tree.get_children())
                self.query_time_label.configure(
                    text=f"✓  Query OK  •  {elapsed:.3f}s  •  {cur.rowcount} affected",
                    text_color=COLORS["success"],
                )
            self._add_history(sql)
            self._set_status(f"Query executed in {elapsed:.3f}s")
        except Exception as e:
            self.query_error.configure(text=f"✗  {e}")
            self.query_time_label.configure(text="")

    def _add_history(self, sql):
        short = sql[:60].replace("\n", " ") + ("…" if len(sql) > 60 else "")
        self.query_history.insert(0, sql)
        self.query_history = self.query_history[:20]
        shorts = [q[:60].replace("\n", " ") + ("…" if len(q) > 60 else "")
                  for q in self.query_history]
        self.history_menu.configure(values=shorts)

    def _load_history(self, selected):
        idx = [
            q[:60].replace("\n", " ") + ("…" if len(q) > 60 else "")
            for q in self.query_history
        ].index(selected)
        self.sql_editor.delete("1.0", "end")
        self.sql_editor.insert("1.0", self.query_history[idx])

    # ── Sorting & Pagination ──────────────────────────────────────────────────
    def _sort_by(self, col):
        if self.sort_col == col:
            self.sort_asc = not self.sort_asc
        else:
            self.sort_col = col
            self.sort_asc = True
        self.current_page = 0
        self._show_table(self.current_table)

    def _next_page(self):
        total_pages = max(1, (self.total_rows + self.page_size - 1) // self.page_size)
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._show_table(self.current_table)

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._show_table(self.current_table)

    # ── Tree Click (sort header) ───────────────────────────────────────────────
    def _on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        if region == "heading":
            col_id = self.tree.identify_column(event.x)
            col_idx = int(col_id.replace("#", "")) - 1
            if col_idx < len(self.all_columns):
                self._sort_by(self.all_columns[col_idx])

    # ── Search ────────────────────────────────────────────────────────────────
    def _search_rows(self, event=None):
        q = self.data_search.get().lower()
        for item in self.tree.get_children():
            vals = self.tree.item(item, "values")
            match = any(q in str(v).lower() for v in vals)
            if not match:
                self.tree.detach(item)
            else:
                self.tree.reattach(item, "", "end")

    # ── Export ────────────────────────────────────────────────────────────────
    def _export_csv(self):
        if not self.conn or not self.current_table:
            messagebox.showwarning("Nothing to export",
                                   "Select a table first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"{self.current_table}.csv",
        )
        if not path:
            return
        try:
            cur = self.conn.cursor()
            cur.execute(f'SELECT * FROM "{self.current_table}"')
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(cols)
                writer.writerows(rows)
            self._set_status(f"Exported {len(rows)} rows to {path}")
            messagebox.showinfo("Exported",
                                f"Saved {len(rows):,} rows to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def on_close(self):
        if self.conn:
            self.conn.close()
        self.destroy()


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = SQLiteViewer()
    app.protocol("WM_DELETE_WINDOW", app.on_close)
    app.mainloop()