from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db import init_db


if __name__ == "__main__":
    init_db()
    print("Banco SQLite inicializado com sucesso.")
