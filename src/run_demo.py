from __future__ import annotations
from .config import RAW_PATH, SEED
from .etl import load_orders_csv
from .seed_master import seed_and_save
from . import tps
from .kpis import run_kpis

def main():
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"No encuentro {RAW_PATH}. Coloca restaurant_orders.csv en la raíz o cambia RAW_PATH en config.py")

    df_raw = load_orders_csv(RAW_PATH)

    # 1) crear tablas + 2) sembrar maestros sintéticos
    tps.init_tables()
    seed_and_save(df_raw, seed=SEED)

    # 3) importar transacciones reales
    n = tps.import_real_transactions(df_raw)
    print("Órdenes reales importadas:", n)

    # 4) demo TPS nuevo -> ERP+SCM
    products = __import__("pandas").read_csv("tables_csv/products.csv")
    sample = products.sample(3, random_state=SEED)["product_id"].tolist()

    oid = tps.create_order("Cliente Demo", branch_id=1, payment_method="Cash")
    tps.add_item(oid, int(sample[0]), 2)
    tps.add_item(oid, int(sample[1]), 1)
    tps.add_item(oid, int(sample[2]), 3)
    result = tps.checkout(oid)
    print("✅ Pedido demo pagado:", result)

    # 5) KPIs
    run_kpis()

if __name__ == "__main__":
    main()
