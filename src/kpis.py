from __future__ import annotations
import os
import pandas as pd
import matplotlib.pyplot as plt
from .config import FIG_DIR
from .storage import read_table

def run_kpis():
    orders = read_table("orders")
    items = read_table("order_items")
    prod = read_table("products")
    pos = read_table("purchase_orders")
    inv = read_table("inventory")

    if orders.empty:
        print("No hay órdenes para KPIs.")
        return

    orders["order_ts"] = pd.to_datetime(orders["order_ts"], errors="coerce")
    orders["order_hour"] = orders["order_ts"].dt.hour
    orders["total_amount"] = pd.to_numeric(orders["total_amount"], errors="coerce").fillna(0.0)

    o_by_hour = orders.groupby("order_hour")["order_id"].count().reindex(range(24), fill_value=0)
    plt.figure()
    o_by_hour.plot(kind="bar")
    plt.title("Pedidos por hora")
    plt.xlabel("Hora"); plt.ylabel("# Pedidos")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "kpi_pedidos_por_hora.png", dpi=160)
    plt.show()

    items["quantity"] = pd.to_numeric(items["quantity"], errors="coerce").fillna(0).astype(int)
    menu = items.merge(prod, on="product_id", how="left")
    top_qty = menu.groupby("food_item")["quantity"].sum().sort_values(ascending=False).head(10)
    plt.figure()
    top_qty.sort_values().plot(kind="barh")
    plt.title("Top 10 productos por cantidad")
    plt.xlabel("Cantidad")
    plt.tight_layout()
    plt.savefig(FIG_DIR / "kpi_top_cantidad.png", dpi=160)
    plt.show()

    # resumen inventario bajo
    inv["stock_on_hand"] = pd.to_numeric(inv["stock_on_hand"], errors="coerce").fillna(0).astype(int)
    inv["stock_min"] = pd.to_numeric(inv["stock_min"], errors="coerce").fillna(0).astype(int)
    low = inv[inv["stock_on_hand"] < inv["stock_min"]].merge(prod[["product_id","food_item","category"]], on="product_id", how="left")
    print("Items bajo mínimo (primeros 10):")
    print(low.head(10))

    if not pos.empty:
        c = pos.groupby("status")["po_id"].count()
        plt.figure()
        c.plot(kind="bar")
        plt.title("Órdenes de compra por estado")
        plt.xlabel("Estado"); plt.ylabel("# Órdenes")
        plt.tight_layout()
        plt.savefig(FIG_DIR / "kpi_oc_por_estado.png", dpi=160)
        plt.show()

    print("✅ Figuras guardadas en:", FIG_DIR)
