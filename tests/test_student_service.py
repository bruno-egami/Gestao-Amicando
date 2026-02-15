
import pytest
import pandas as pd
from datetime import date
from services import student_service, material_service

def setup_student_and_class(db_conn):
    # Setup Class (Segunda-feira = 0)
    class_id = student_service.create_class(db_conn, "Turma Seg", "14:00", "Segundas", weekday=0)
    
    # Setup Student
    student_id = student_service.create_student(db_conn, "Aluno Teste", "123456", class_id=class_id, join_date="2024-01-01")
    
    # Setup Price
    student_service.set_global_price_per_class(db_conn, 80.0)
    
    return student_id, class_id

def test_calculate_tuition_basic(db_conn):
    student_id, class_id = setup_student_and_class(db_conn)
    
    # May 2024 has 4 Mondays (May 6, 13, 20, 27)
    # Wait, calendar.monthcalendar(2024, 5) 
    # [ [0, 0, 1, 2, 3, 4, 5], 
    #   [6, 7, 8, 9, 10, 11, 12], 
    #   [13, 14, 15, 16, 17, 18, 19], 
    #   [20, 21, 22, 23, 24, 25, 26], 
    #   [27, 28, 29, 30, 31, 0, 0] ]
    # Yes, 4 Mondays.
    
    count, price, total, dates = student_service.calculate_tuition(db_conn, student_id, "05/2024")
    
    assert count == 4
    assert price == 80.0
    assert total == 320.0
    assert len(dates) == 4

def test_calculate_tuition_with_cancellation(db_conn):
    student_id, class_id = setup_student_and_class(db_conn)
    
    # Cancel May 13th, 2024
    student_service.add_class_cancellation(db_conn, class_id, "2024-05-13", "Feriado")
    
    count, price, total, dates = student_service.calculate_tuition(db_conn, student_id, "05/2024")
    
    assert count == 3
    assert total == 240.0
    assert "2024-05-13" not in dates

def test_process_material_consumption(db_conn, mock_auth):
    student_id, _ = setup_student_and_class(db_conn)
    
    # Setup Material
    mat_id = material_service.create_material(db_conn, "Argila", None, None, 10.0, "kg", 100.0, 0.0, "Material")
    
    # Process consumption: 2kg with 50% markup (Price 10 -> 15)
    # Total = 2 * 15 = 30
    success = student_service.process_material_consumption(
        db_conn, student_id, mat_id, 2.0, "2024-05-01", user_id=1, notes="Teste", markup=50.0
    )
    assert success  # Should be the consumption ID
    
    # Check Stock
    mat = material_service.get_material_by_id(db_conn, mat_id)
    assert mat['stock_level'] == 98.0
    
    # Check Financial Summary
    summary = student_service.get_student_financial_summary(db_conn, student_id)
    # (tuitions_df, consumptions_df, total_due)
    consumptions_df = summary[1]
    assert len(consumptions_df) == 1
    assert consumptions_df.iloc[0]['total_value'] == 30.0
    assert summary[2] == 30.0 # total_due

def test_partial_payment_allocation(db_conn):
    student_id, _ = setup_student_and_class(db_conn)
    
    # Add two debts
    # 1. Tuition R$ 320
    student_service.generate_tuition_record(db_conn, student_id, "05/2024", 320.0)
    # 2. Consumption R$ 30
    student_service.add_consumption(db_conn, student_id, "Extra", 1, 30.0, 30.0, "2024-05-01", user_id=1)
    
    # Pay R$ 330
    # Should pay Tuition (320) fully and Consumption (10) partially.
    # Remaining Debt = 20.0
    student_service.process_partial_payment(db_conn, student_id, 330.0)
    
    summary = student_service.get_student_financial_summary(db_conn, student_id)
    assert summary[2] == 20.0 # total_due
