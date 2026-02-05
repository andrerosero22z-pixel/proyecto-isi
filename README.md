# ISID223 — Proyecto Final (TPS + ERP + SCM + BI/RFM) **sin SQLite**
Plantilla **desde cero** con persistencia en **CSV** (mini “base de datos”), datos sintéticos controlados e integración automática.

## 1) Requisitos
- Python 3.10+
- pandas, numpy, matplotlib

Instalación (local):
```bash
pip install -r requirements.txt
```

## 2) Dataset real
Coloca tu archivo **restaurant_orders.csv** en la carpeta raíz del proyecto (misma carpeta que este README) o ajusta la ruta en `src/config.py`.

## 3) Ejecutar demo (crea tablas + importa pedidos reales + corre TPS→ERP→SCM + KPIs)
```bash
python -m src.run_demo
``` py -m streamlit run app.py

## 4) Qué crea en `tables_csv/`
- `branches.csv`, `suppliers.csv`, `products.csv`, `inventory.csv`  (sintético)
- `customers.csv`, `orders.csv`, `order_items.csv` (TPS)
- `ledger_entries.csv` (ERP)
- `stock_movements.csv`, `purchase_orders.csv`, `purchase_order_items.csv` (SCM)

## 5) Para el informe (texto listo)
Mira el bloque `REPORT_TEXT` en `src/report_text.py`.

