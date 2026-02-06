#  Verona Restaurant
### Sistema TPS + ERP + SCM + KPIs + RFM  
**Python · Streamlit · CSV**

Proyecto académico que simula el funcionamiento integral de un restaurante usando archivos CSV como base de datos.  
Incluye ventas (TPS), contabilidad básica (ERP), inventario y compras (SCM), dashboards de KPIs y segmentación RFM.

---

## 📌 Requisitos

- Python **3.10 o superior**
- pip
- Sistema operativo: Windows / Linux / macOS

---

## 📦 Instalación

### 1️⃣ (Opcional) Crear entorno virtual

**Windows**
```bash
py -m venv .venv
.\.venv\Scripts\activate
```

**Linux / macOS**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

### 2️⃣ Instalar dependencias

```bash
pip install streamlit pandas matplotlib
```

---

## 📂 Estructura del proyecto

```text
verona-restaurant/
│
├── app.py
└── tables_csv/
    ├── customers.csv
    ├── products.csv
    ├── branches.csv
    ├── suppliers.csv
    ├── inventory.csv
    ├── orders.csv
    ├── order_items.csv
    ├── purchase_orders.csv
    ├── purchase_order_items.csv
    ├── ledger_entries.csv
    └── rfm_customers.csv
```

---

## ▶️ Ejecución

```bash
py -m streamlit run app.py
```

Navegador:
```text
http://localhost:8501
```

---

## 🔄 Flujo del sistema

1. TPS: crear pedido, agregar items, checkout  
2. ERP: registra ingresos y costos  
3. SCM: descuenta stock y alerta mínimos  
4. SCM: crear y recibir órdenes de compra  
5. BI: KPIs y RFM automáticos  

---

## 📊 KPIs incluidos
- Pedidos por hora
- Ingresos por hora
- Top productos
- Ventas por categoría
- Método de pago

---

## 🎯 RFM
- Recency, Frequency, Monetary
- Scores 1–5
- Segmentos automáticos
- Exporta CSV

---
