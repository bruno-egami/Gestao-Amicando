
import pytest
import pandas as pd
from services import product_service

def test_get_all_products_no_filters(db_conn):
    # Insert dummy data
    db_conn.execute("INSERT INTO products (name, category, base_price, stock_quantity) VALUES (?, ?, ?, ?)", 
                   ("Vaso A", "Vaso", 50.0, 10))
    db_conn.execute("INSERT INTO products (name, category, base_price, stock_quantity) VALUES (?, ?, ?, ?)", 
                   ("Caneca B", "Louça", 25.0, 20))
    db_conn.commit()
    
    df = product_service.get_all_products(db_conn)
    assert len(df) == 2
    assert "thumb_path" in df.columns

def test_get_all_products_search_filter(db_conn):
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("Vaso Grande", "Vaso"))
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("Vaso Pequeno", "Vaso"))
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("Caneca", "Louça"))
    db_conn.commit()
    
    # Search for 'Vaso'
    df = product_service.get_all_products(db_conn, search_term="Vaso")
    assert len(df) == 2
    assert all("Vaso" in name for name in df['name'])

def test_get_all_products_category_filter(db_conn):
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("Vaso", "Vaso"))
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("Caneca", "Louça"))
    db_conn.commit()
    
    # Single category
    df = product_service.get_all_products(db_conn, category="Vaso")
    assert len(df) == 1
    assert df.iloc[0]['category'] == "Vaso"
    
    # Multiple categories (List)
    df_list = product_service.get_all_products(db_conn, category=["Vaso", "Louça"])
    assert len(df_list) == 2

def test_get_categories(db_conn):
    # Seeded categories exist, clearing for precise test
    db_conn.execute("DELETE FROM product_categories")
    
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("P1", "Cat A"))
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("P2", "Cat B"))
    db_conn.execute("INSERT INTO products (name, category) VALUES (?, ?)", ("P3", "Cat A"))
    db_conn.commit()
    
    # Fetch categories from products
    cats = product_service.get_categories(db_conn)
    assert "Cat A" in cats
    assert "Cat B" in cats
    assert len(cats) == 2 # Cat A + Cat B
