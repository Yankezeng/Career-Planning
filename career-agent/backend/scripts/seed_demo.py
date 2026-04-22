from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.core.database import init_db
from app.core.seed_runtime import seed_demo_data


if __name__ == "__main__":
    init_db()
    seed_demo_data()
    print("Demo data seeded.")
