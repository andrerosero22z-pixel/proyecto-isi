from __future__ import annotations
import os
from pathlib import Path

SEED = 42

# ✅ Cambia esta ruta si tu CSV está en otro lugar
RAW_PATH = Path("restaurant_orders.csv")

BASE_DIR = Path(".")
TABLE_DIR = BASE_DIR / "tables_csv"
FIG_DIR = BASE_DIR / "figures"

TABLE_DIR.mkdir(exist_ok=True)
FIG_DIR.mkdir(exist_ok=True)
