from __future__ import annotations
import pandas as pd
from pathlib import Path
from .config import TABLE_DIR

def tpath(name: str) -> Path:
    return TABLE_DIR / f"{name}.csv"

def read_table(name: str) -> pd.DataFrame:
    p = tpath(name)
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

def write_table(name: str, df: pd.DataFrame) -> None:
    df.to_csv(tpath(name), index=False)

def append_table(name: str, df_new: pd.DataFrame) -> None:
    df_old = read_table(name)
    if df_old.empty:
        write_table(name, df_new)
    else:
        write_table(name, pd.concat([df_old, df_new], ignore_index=True))

def ensure_table(name: str, columns: list[str]) -> None:
    p = tpath(name)
    if not p.exists():
        write_table(name, pd.DataFrame(columns=columns))

def next_id(name: str, id_col: str, start: int = 1) -> int:
    df = read_table(name)
    if df.empty or id_col not in df.columns:
        return start
    mx = pd.to_numeric(df[id_col], errors="coerce").max()
    return start if pd.isna(mx) else int(mx) + 1
