
import pytest
import pandas as pd
from datetime import date, timedelta
from services import sales_service, product_service, order_service

def test_complete_sales_transaction_split(db_conn, mock_auth):
    # Setup
    # 1. Product In Stock (10 units)
    db_conn.execute("INSERT INTO products (id, name, base_price, stock_quantity) VALUES (1, 'Vaso', 100.0, 10)")
    # 2. Product Out of Stock (0 units)
    db_conn.execute("INSERT INTO products (id, name, base_price, stock_quantity) VALUES (2, 'Caneca', 50.0, 0)")
    # 3. Client
    client_id = 99
    db_conn.execute("INSERT INTO clients (id, name) VALUES (99, 'Cliente Teste')")
    db_conn.commit()

    # Cart Analysis (Simulating the logic from the Vendas UI)
    cart_analysis = [
        {
            'item': {
                'product_id': 1,
                'name': 'Vaso',
                'qty': 5, # Buy 5 (immediate)
                'base_price': 100.0,
                'discount': 0.0
            },
            'can_sell': 5,
            'must_order': 0
        },
        {
            'item': {
                'product_id': 2,
                'name': 'Caneca',
                'qty': 3, # Buy 3 (must order)
                'base_price': 50.0,
                'discount': 0.0
            },
            'can_sell': 0,
            'must_order': 3
        }
    ]

    # Process Transaction
    result = sales_service.process_sale_transaction(
        db_conn, 
        cart_analysis, 
        client_id=client_id, 
        salesperson="Admin", 
        payment_method="Pix", 
        notes="Integração", 
        delivery_days=7, 
        deposit_val=50.0 # R$ 50 deposit
    )

    assert result['success'] is True
    assert result['order_id'] is not None # Commission order created for item 2

    # Verification:
    # 1. Item 1 Stock should be 5 (10 - 5)
    row_mat1 = db_conn.execute("SELECT stock_quantity FROM products WHERE id=1").fetchone()
    assert row_mat1[0] == 5

    # 2. Immediate Sale should be recorded in 'sales'
    sales_df = pd.read_sql("SELECT * FROM sales WHERE product_id=1", db_conn)
    assert len(sales_df) == 1
    assert sales_df.iloc[0]['quantity'] == 5
    assert sales_df.iloc[0]['total_price'] == 500.0

    # 3. Deposit Sale should be recorded (product_id is None for deposits usually)
    deposit_sales = pd.read_sql("SELECT * FROM sales WHERE product_id IS NULL", db_conn)
    assert len(deposit_sales) == 1
    assert deposit_sales.iloc[0]['total_price'] == 50.0

    # 4. Commission Order should exist with 3 Canecas
    order_items = pd.read_sql("SELECT * FROM commission_items WHERE order_id=?", db_conn, params=(result['order_id'],))
    assert len(order_items) == 1
    assert order_items.iloc[0]['product_id'] == 2
    assert order_items.iloc[0]['quantity'] == 3
