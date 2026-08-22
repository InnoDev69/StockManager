from main import app
import os

if __name__ == "__main__":
    os.environ["DEBUG"] = "1"
    app.config["SECRET_KEY"] = "dev"
    app.config["DEBUG_TB_ENABLED"] = True
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        use_reloader=True
    )