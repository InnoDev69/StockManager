tables = {
    "users_table_query": """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            status INTEGER NOT NULL DEFAULT 1,
            application TEXT NOT NULL DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            history TEXT
        )
        """,
        
    "items_table_query": """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY NOT NULL,
            barrs_code TEXT UNIQUE,
            description TEXT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            min_quantity INTEGER NOT NULL DEFAULT 5,
            price REAL NOT NULL,
            expiration_date TEXT,
            status INTEGER NOT NULL DEFAULT 1,
            notified_low_stock INTEGER NOT NULL DEFAULT 0,
            created_at TEXT,
            updated_at TEXT
        )
        """,
        
    "sells_table_query": """
        CREATE TABLE IF NOT EXISTS sells (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            vendor_id INTEGER NOT NULL REFERENCES users(id),
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """,
        
    "sells_details_table_query": """
        CREATE TABLE IF NOT EXISTS details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            vendor_id INTEGER NOT NULL REFERENCES users(id),
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (item_id) REFERENCES items (id)
        )
        """,
        
    "reset_codes_table_query": """
        CREATE TABLE IF NOT EXISTS password_resets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        
    "item_attributes_table_query": """
        CREATE TABLE IF NOT EXISTS item_attributes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            data_type TEXT NOT NULL,
            required INTEGER NOT NULL DEFAULT 0,
            status INTEGER NOT NULL DEFAULT 1
        )
        """,
        
    "item_attribute_values_table_query": """
        CREATE TABLE IF NOT EXISTS item_attribute_values (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            attribute_id INTEGER NOT NULL,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(item_id, attribute_id),
            FOREIGN KEY (item_id) REFERENCES items(id),
            FOREIGN KEY (attribute_id) REFERENCES item_attributes(id)
        )
        """,
        
    "notifications_table_query": """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            type TEXT DEFAULT 'info' CHECK(type IN ('info', 'warning', 'success', 'error')),
            action_url TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """,
        
    "audit_log_table_query": """
        CREATE TABLE IF NOT EXISTS audit_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            action      TEXT    NOT NULL,
            entity_type TEXT    NOT NULL,
            entity_id   INTEGER,
            old_value   TEXT,
            new_value   TEXT,
            description TEXT,
            ip_address  TEXT,
            timestamp   TEXT    DEFAULT CURRENT_TIMESTAMP,
            status      TEXT    DEFAULT 'success',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        
    "customers_table_query": """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            credit_limit REAL,
            status INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,

    "account_movements_table_query": """
        CREATE TABLE IF NOT EXISTS account_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            sell_id INTEGER,
            type TEXT NOT NULL CHECK(type IN ('DEBT', 'PAYMENT', 'ADJUSTMENT')),
            amount REAL NOT NULL,
            date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER NOT NULL,
            note TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id),
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """,
        
    "weight_items_table_query": """
        CREATE TABLE IF NOT EXISTS weight_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            weight REAL NOT NULL,
            price REAL NOT NULL,
            price_per_gram REAL NOT NULL,  -- gramos de referencia para 'price', ej: 500 = precio cada 500g
            description TEXT,
            status INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
 
    "weight_details_table_query": """
        CREATE TABLE IF NOT EXISTS weight_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sell_id INTEGER NOT NULL,
            weight_item_id INTEGER NOT NULL,
            weight REAL NOT NULL,
            price REAL NOT NULL,
            vendor_id INTEGER NOT NULL REFERENCES users(id),
            payment_method TEXT NOT NULL DEFAULT 'Efectivo',
            FOREIGN KEY (sell_id) REFERENCES sells (id),
            FOREIGN KEY (weight_item_id) REFERENCES weight_items (id)
        )
        """,
}