
import pytest
import pandas as pd
from services import material_service

def test_create_and_get_material(db_conn):
    # Setup: Create categories and suppliers
    cat_id = material_service.create_category(db_conn, "Argilas")
    sup_id = db_conn.cursor().execute("INSERT INTO suppliers (name) VALUES (?)", ("Fornecedor A",)).lastrowid
    
    # Test Create
    mat_id = material_service.create_material(
        db_conn, "Argila Branca", cat_id, sup_id, 50.0, "kg", 10.0, 2.0, "Material"
    )
    assert mat_id > 0
    
    # Test Get
    mat = material_service.get_material_by_id(db_conn, mat_id)
    assert mat['name'] == "Argila Branca"
    assert mat['stock_level'] == 10.0

def test_register_entry_weighted_average(db_conn, mock_auth):
    cat_id = material_service.create_category(db_conn, "Esmaltes")
    mat_id = material_service.create_material(
        db_conn, "Esmalte Base", cat_id, None, 100.0, "kg", 10.0, 2.0, "Material"
    )
    
    # 10kg at R$ 100.00 = R$ 1000 total
    # Add 10kg at R$ 200.00 = R$ 2000 total
    # Total 20kg, Total R$ 3000 -> New Avg = R$ 150.00
    
    new_stock, new_price = material_service.register_entry(db_conn, mat_id, 10.0, 2000.0, "Compra nova", 1)
    
    assert new_stock == 20.0
    assert new_price == 150.0

def test_stock_precision_fix(db_conn, mock_auth):
    """Verifies the fix for floating point precision (3.900...04)"""
    mat_id = material_service.create_material(
        db_conn, "Esmalte Teste", None, None, 75.0, "kg", 5.0, 0.0, "Material"
    )
    
    # 5.0 - 0.1 - 1.0 = 3.9
    material_service.register_exit(db_conn, mat_id, 0.1, "Saída 1", 1)
    new_stock = material_service.register_exit(db_conn, mat_id, 1.0, "Saída 2", 1)
    
    # Should be exactly 3.9, not 3.9000000000000004
    assert new_stock == 3.9
    
    # Verify via DB direct query to ensure it's not just a pandas representation
    db_val = db_conn.execute("SELECT stock_level FROM materials WHERE id = ?", (mat_id,)).fetchone()[0]
    assert db_val == 3.9

def test_get_all_materials_filtering(db_conn):
    cat_a = material_service.create_category(db_conn, "Cat A")
    cat_b = material_service.create_category(db_conn, "Cat B")
    
    material_service.create_material(db_conn, "Mat 1", cat_a, None, 10.0, "kg", 5.0, 0.0, "Material")
    material_service.create_material(db_conn, "Mat 2", cat_b, None, 10.0, "kg", 5.0, 0.0, "Material")
    
    # Filter by Category
    df_filtered = material_service.get_all_materials(db_conn, {"category": "Cat A"})
    assert len(df_filtered) == 1
    assert df_filtered.iloc[0]['name'] == "Mat 1"
    
    # Search filter
    df_search = material_service.get_all_materials(db_conn, {"search": "Mat 2"})
    assert len(df_search) == 1
    assert df_search.iloc[0]['name'] == "Mat 2"
