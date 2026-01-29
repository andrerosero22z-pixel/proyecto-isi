REPORT_TEXT = """El dataset restaurant_orders.csv se utilizó como fuente real de transacciones históricas, incluyendo: identificador de orden,
nombre del cliente, ítem del menú, categoría, cantidad, precio unitario, método de pago y marca de tiempo del pedido.
A partir de estos campos, se calcularon variables derivadas necesarias para el análisis (por ejemplo: line_total, order_hour, day_of_week).

Debido a que el CSV no incluye información operativa típica de una cadena de restaurantes (inventarios por sucursal, proveedores,
costos de los ítems, ni órdenes de compra), se generaron datos sintéticos controlados para simular la integración entre sistemas:
(1) tres sucursales como unidades operativas; (2) un proveedor por categoría con lead time 1–4 días; (3) costos unitarios estimados
aplicando un margen controlado (35%–60%) sobre el precio de venta con semilla fija para reproducibilidad; y (4) inventario inicial
por producto y sucursal basado en demanda histórica, además de stock_min y reorder_qty para reabastecimiento automático.
Finalmente, al confirmar el pago (checkout), el TPS cambia el estado de la orden y dispara automáticamente el registro contable
en ERP (REVENUE/COGS) y la actualización de inventario en SCM; si el stock cae bajo mínimo, se genera una orden de compra al proveedor.
"""
