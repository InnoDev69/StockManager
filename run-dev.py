from main import app
from tools.email import email_sender
import os

if __name__ == "__main__":
    os.environ["DEBUG"] = "1"
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )