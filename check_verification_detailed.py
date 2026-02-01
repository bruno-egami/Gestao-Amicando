import sqlite3
import pandas as pd
import os
import json

DB_PATH = r"d:\GitHub\Gestao-Amicando\data\ceramic_admin.db"

def query_db():
    conn = sqlite3.connect(DB_PATH)
    
    print("\n=== VERIFICAÇÃO ORÇAMENTO ORC-260201-19 ===")
    quote = pd.read_sql("SELECT * FROM quotes WHERE id = 19", conn)
    if quote.empty:
        print("Erro: Orçamento 19 não encontrado.")
    else:
        q = quote.iloc[0]
        print(f"Status: {q['status']}")
        print(f"Total: R$ {q['total_price']:.2f} (Desconto: R$ {q['discount']:.2f})")
        print(f"Pedido Convertido ID: {q['converted_order_id']}")

    print("\n--- Itens do Orçamento ---")
    quote_items = pd.read_sql("""
        SELECT qi.*, p.name 
        FROM quote_items qi 
        JOIN products p ON qi.product_id = p.id 
        WHERE qi.quote_id = 19
    """, conn)
    for _, it in quote_items.iterrows():
        print(f"- {it['name']} (ID: {it['product_id']}): Qtd {it['quantity']}, Preço Unit: R$ {it['unit_price']:.2f}")

    print("\n=== VERIFICAÇÃO ENCOMENDA ENC-260201-39 ===")
    order = pd.read_sql("SELECT * FROM commission_orders WHERE id = 39", conn)
    if order.empty:
        print("Erro: Encomenda 39 não encontrada.")
    else:
        o = order.iloc[0]
        print(f"Status: {o['status']}")
        print(f"Total: R$ {o['total_price']:.2f} (Desconto Manual: R$ {o['manual_discount']:.2f}, Sinal: R$ {o['deposit_amount']:.2f})")

    print("\n--- Itens da Encomenda ---")
    # Note: query uses notes instead of item_notes because database.py says commission_items has notes
    order_items = pd.read_sql("""
        SELECT ci.*, p.name 
        FROM commission_items ci 
        JOIN products p ON ci.product_id = p.id 
        WHERE ci.order_id = 39
    """, conn)
    
    for _, it in order_items.iterrows():
        # Handle binary if necessary (though pandas usually handles it)
        print(f"- {it['name']} (ID: {it['product_id']}): Qtd {it['quantity']}, Reservado: {it['quantity_from_stock']}, Produzido: {it['quantity_produced']}, Preço Unit: R$ {it['unit_price']:.2f}")

    print("\n=== VERIFICAÇÃO DE VENDAS (BAIXA DE ESTOQUE) ===")
    sales = pd.read_sql("SELECT * FROM sales WHERE order_id LIKE '%-39'", conn)
    if sales.empty:
        print("Nenhuma venda encontrada para ENC-39.")
    else:
        for _, s in sales.iterrows():
            print(f"- Venda ID: {s['id']}, Data: {s['date']}, Produto ID: {s['product_id']}, Qtd: {s['quantity']}, Total: R$ {s['total_price']:.2f}, Status: {s['status']}")

    print("\n=== HISTÓRICO DE PRODUÇÃO ===")
    prod_hist = pd.read_sql("SELECT * FROM production_history WHERE order_id = 39", conn)
    if prod_hist.empty:
        print("Nenhum histórico de produção encontrado.")
    else:
        for _, p in prod_hist.iterrows():
            print(f"- {p['timestamp']}: Produção de {p['quantity']}x {p['product_name']} (ID Prod: {p['product_id']})")

    print("\n=== AUDIT LOG (DETALHES) ===")
    audit = pd.read_sql("""
        SELECT * FROM audit_log 
        WHERE (table_name = 'commission_orders' AND record_id = 39)
           OR (table_name = 'sales' AND record_id IN (SELECT id FROM sales WHERE order_id LIKE '%-39'))
           OR (table_name = 'products' AND action = 'UPDATE')
        ORDER BY timestamp DESC LIMIT 20
    """, conn)
    
    # Filter products updates to only include those relevant if possible, 
    # but since we don't know the product ID for sure from the previous output let's just show recent ones.
    print(audit[['timestamp', 'action', 'table_name', 'record_id', 'old_data', 'new_data']])

    conn.close()

if __name__ == "__main__":
    query_db()
