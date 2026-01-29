from __future__ import annotations
import pandas as pd

def load_orders_csv(path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0.0)

    df["order_ts"] = pd.to_datetime(df["order_time"], errors="coerce")
    df["order_date"] = df["order_ts"].dt.date.astype(str)
    df["order_hour"] = df["order_ts"].dt.hour
    df["day_of_week"] = df["order_ts"].dt.day_name()
    df["line_total"] = df["quantity"] * df["price"]
    return df
