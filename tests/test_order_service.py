
import pytest
import pandas as pd
from datetime import date, timedelta
from services import order_service

def setup_orders(db_conn):
    # Setup Clients
    db_conn.execute("INSERT INTO clients (name) VALUES (?)", ("Cliente A",))
    db_conn.execute("INSERT INTO clients (name) VALUES (?)", ("Cliente B",))
    
    # Setup Orders
    # ID 1: Cliente A, Pendente, Vencimento Hoje - 1
    db_conn.execute("""
        INSERT INTO commission_orders (client_id, status, date_due, total_price, date_created) 
        VALUES (1, 'Pendente', ?, 100.0, ?)
    """, ((date.today() - timedelta(days=1)).isoformat(), date.today().isoformat()))
    
    # ID 2: Cliente B, Concluído, Vencimento Hoje + 1
    db_conn.execute("""
        INSERT INTO commission_orders (client_id, status, date_due, total_price, date_created) 
        VALUES (2, 'Concluído', ?, 200.0, ?)
    """, ((date.today() + timedelta(days=1)).isoformat(), date.today().isoformat()))
    db_conn.commit()

def test_get_orders_no_filters(db_conn):
    setup_orders(db_conn)
    df = order_service.get_orders_for_management(db_conn)
    assert len(df) == 2

def test_get_orders_status_filter(db_conn):
    setup_orders(db_conn)
    # Status filter is a list
    df = order_service.get_orders_for_management(db_conn, {"status": ["Pendente"]})
    assert len(df) == 1
    assert df.iloc[0]['status'] == "Pendente"

def test_get_orders_client_filter(db_conn):
    setup_orders(db_conn)
    df = order_service.get_orders_for_management(db_conn, {"client": "Cliente B"})
    assert len(df) == 1
    assert df.iloc[0]['client'] == "Cliente B"

def test_get_orders_date_filter(db_conn):
    setup_orders(db_conn)
    # Start date filter
    df_start = order_service.get_orders_for_management(db_conn, {"start_date": date.today().isoformat()})
    assert len(df_start) == 1
    assert df_start.iloc[0]['client'] == "Cliente B" # Only the one due tomorrow
    
    # End date filter
    df_end = order_service.get_orders_for_management(db_conn, {"end_date": (date.today() - timedelta(days=1)).isoformat()})
    assert len(df_end) == 1
    assert df_end.iloc[0]['client'] == "Cliente A"
