# StockManager

> Professional inventory and sales management system with native desktop interface

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)

## Description

StockManager is a desktop application for comprehensive inventory and sales management, designed for small and medium businesses that need complete control over their inventory without configuration complications.

### Main Features

- **Intuitive Dashboard**: Overview with real-time metrics
- **Authentication System**: Role-based access control
- **Product Management**: Complete CRUD with barcodes
- **Sales Registration**: Fast processing with automatic updates
- **Metrics and Reports**: Sales analysis and trends
- **CSV Import**: Bulk product loading
- **Advanced Search**: Multi-criteria filtering
- **Responsive Interface**: Adaptable to different screens
- **Security**: Hashed passwords and exhaustive validation

## Quick Start

### Requirements

- **Python 3.8+**
- **pip** (package manager)
- **SQLite 3** (included in Python)

### Installation

```bash
# 1. Clone repository
git clone https://github.com/InnoDev69/StockManager.git
cd StockManager

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run application
python main.py
```

The application will automatically open in a native window at `http://127.0.0.1:5000`

### First Use

1. **Register**: Create account on registration screen
2. **Login**: Sign in with credentials
3. **Add Products**: Navigate to "New Product"
4. **Register Sales**: Use sales form
5. **View Dashboard**: Monitor statistics

## Documentation

### For Developers

- **[Spanish](docs/es/README.md)** - Complete documentation in Spanish
- **[English](docs/en/README.md)** - Complete documentation in English

#### Main Guides

- [Architecture](docs/en/ARCHITECTURE.md) - System design
- [Development](docs/en/DEVELOPMENT.md) - Environment setup
- [REST API](docs/en/API.md) - Endpoints and examples
- [Database](docs/en/DATABASE.md) - Schema and queries
- [Security](docs/en/SECURITY_ROLES.md) - Roles and permissions
- [Deployment](docs/en/DEPLOYMENT.md) - Packaging
- [Troubleshooting](docs/en/TROUBLESHOOTING.md) - Solutions

## Architecture

```
┌─────────────────────────────────────┐
│      PyWebView Window               │
│  ┌───────────────────────────────┐  │
│  │    Web UI (HTML/CSS/JS)       │  │
│  └───────────────────────────────┘  │
└─────────────┬───────────────────────┘
              ↕ HTTP
    http://127.0.0.1:5000
              ↕
┌─────────────▼───────────────────────┐
│       Flask Application             │
│  ┌──────────┐    ┌───────────────┐ │
│  │   UI     │    │   REST API    │ │
│  │ (Jinja2) │    │   (/api/*)    │ │
│  └──────────┘    └───────────────┘ │
└─────────────┬───────────────────────┘
              ↕
┌─────────────▼───────────────────────┐
│      SQLite Database                │
│      (database.db)                  │
└─────────────────────────────────────┘
```

**Components:**
- **Frontend**: PyWebView (native window) + HTML/CSS/JS
- **Backend**: Flask 3.0.0 (Python)
- **Database**: SQLite 3 with WAL mode
- **API**: REST JSON endpoints

See [ARCHITECTURE.md](docs/en/ARCHITECTURE.md) for complete details.

## REST API

The application exposes a complete REST API:

### Main Endpoints

```http
GET  /api/health              # Server status
GET  /api/products            # List active products
GET  /api/products/:id        # Get product
POST /api/products            # Create product (admin)
PUT  /api/products/:id        # Update product (admin)
DELETE /api/products/:id      # Delete product (admin)
POST /api/sales               # Register sale
GET  /api/sales               # Sales history
GET  /api/stats               # Dashboard statistics
```

**Example:**
```javascript
// Get products
fetch('/api/products')
  .then(r => r.json())
  .then(products => console.log(products));
```

See [complete API documentation](docs/en/API.md)

## Technologies

### Backend
- **Python 3.8+**
- **Flask 3.0.0** - Web framework
- **SQLite 3** - Database
- **Werkzeug 3.0.1** - Security
- **PyWebView** - Desktop wrapper

### Frontend
- **HTML5 + Jinja2** - Templates
- **CSS3** - Styles (vanilla)
- **JavaScript ES6+** - Interactivity
- **Fetch API** - AJAX requests

## Project Structure

```
StockManager/
├── main.py                 # Main entrypoint
├── requirements.txt        # Python dependencies
├── .gitignore             # Ignored files
│
├── api/
│   └── API.py             # REST API Blueprint
│
├── bd/                     # Database layer
│   ├── bdConector.py      # SQLite connector
│   ├── bdInstance.py      # Global instance
│   └── bdErrors.py        # Exceptions
│
├── data/                   # Validation
│   ├── validators.py      # Validators
│   └── limits.py          # Limits
│
├── tools/                  # Utilities
│   ├── logger.py          # Logging system
│   ├── scheduler.py       # Periodic tasks
│   └── timmer.py          # Performance measurement
│
├── templates/              # HTML templates
│   ├── dashboard.html     # Main dashboard
│   ├── login.html         # Login/Register
│   └── ...
│
├── static/                 # Static assets
│   ├── css/
│   ├── js/
│   └── app/               # Icons
│
└── docs/                   # Documentation
    ├── es/                # Spanish
    └── en/                # English
```

## Security

- Passwords: Hashed with PBKDF2:SHA256
- Sessions: Signed cookies
- Validation: All inputs validated
- SQL Injection: Parameterized queries
- Foreign Keys: Referential integrity
- CSRF: Flask native protection

## Contributing

Contributions are welcome:

1. Fork the repository
2. Create a branch (`git checkout -b feature/NewFeature`)
3. Commit changes (`git commit -m 'Add: new feature'`)
4. Push to branch (`git push origin feature/NewFeature`)
5. Open a Pull Request

### Style Guide

- **Python**: PEP 8
- **Docstrings**: Google Style
- **Commits**: Descriptive messages in present tense

## License

This project is under the MIT License. See [LICENSE](LICENSE) file for details.

## Authors

- **InnoDev69** - [GitHub](https://github.com/InnoDev69)

## Support

If you encounter problems:

1. Review [Troubleshooting](docs/en/TROUBLESHOOTING.md)
2. Search in [Issues](https://github.com/InnoDev69/StockManager/issues)
3. Open a [new issue](https://github.com/InnoDev69/StockManager/issues/new)

---

If this project is useful to you, consider giving it a star on GitHub
