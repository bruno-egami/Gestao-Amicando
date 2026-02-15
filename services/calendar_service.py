"""
Calendar Service Module
Handles generation of iCalendar (.ics) files for external calendar integration.
"""
import pandas as pd
import json
from icalendar import Calendar, Event
from datetime import datetime, date, timedelta
from utils.logging_config import get_logger

logger = get_logger(__name__)

def generate_ics_file(conn, start_date=None, end_date=None, categories=None):
    """
    Generates an RFC 5545 compliant iCalendar file.
    
    Args:
        conn: SQLite connection.
        start_date: Start date string (YYYY-MM-DD) or date object.
        end_date: End date string (YYYY-MM-DD) or date object.
        categories: List of categories to export ['Encomendas', 'Aulas'].
        
    Returns:
        bytes: ICS file content.
    """
    if categories is None:
        categories = ['Encomendas', 'Aulas']
        
    cal = Calendar()
    cal.add('prodid', '-//Amicando//Sistema de Gestao//BR')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'Amicando - Gestão de Ateliê')
    cal.add('x-wr-timezone', 'America/Sao_Paulo')

    # 1. ENCOMENDAS (ORDERS)
    if 'Encomendas' in categories:
        try:
            query = """
                SELECT co.id, c.name as client_name, co.date_due, co.status, co.notes,
                       GROUP_CONCAT(ci.quantity || 'x ' || p.name, ', ') as items_summary
                FROM commission_orders co
                JOIN clients c ON co.client_id = c.id
                LEFT JOIN commission_items ci ON co.id = ci.order_id
                LEFT JOIN products p ON ci.product_id = p.id
                WHERE co.status != 'Entregue'
            """
            params = []
            if start_date:
                query += " AND co.date_due >= ?"
                params.append(str(start_date))
            if end_date:
                query += " AND co.date_due <= ?"
                params.append(str(end_date))
            
            query += " GROUP BY co.id"
            orders = pd.read_sql(query, conn, params=params)

            for _, order in orders.iterrows():
                event = Event()
                event.add('summary', f"📦 Encomenda: {order['client_name']}")
                
                # Deterministic UID
                event.add('uid', f"enc_{order['id']}@amicando.com.br")
                
                # Date Processing
                try:
                    due_date = datetime.strptime(order['date_due'], '%Y-%m-%d').date()
                    event.add('dtstart', due_date)
                    # All day event usually doesn't need dtend if it's 1 day, 
                    # but some apps prefer it.
                    event.add('dtend', due_date + timedelta(days=1))
                except Exception:
                    continue
                
                desc = f"Status: {order['status']}\nItens: {order['items_summary'] or '---'}"
                if order['notes']:
                    desc += f"\n\nObs: {order['notes']}"
                
                event.add('description', desc)
                event.add('status', 'CONFIRMED')
                cal.add_component(event)
                
        except Exception as e:
            logger.error(f"Error exporting orders to ICS: {e}")

    # 2. AULAS (CLASSES)
    if 'Aulas' in categories:
        try:
            # We fetch tuitions and expand class_dates
            query = """
                SELECT t.id, s.name as student_name, t.class_dates, t.month_year
                FROM tuitions t
                JOIN students s ON t.student_id = s.id
                WHERE t.class_dates IS NOT NULL AND t.status != 'Cancelado'
            """
            # Filter optimization: since class_dates is JSON, we fetch month/year range
            # or just fetch all active tuitions and filter in python.
            # Usually tuitions are generated for the current/past month.
            
            tuitions = pd.read_sql(query, conn)
            
            for _, t in tuitions.iterrows():
                try:
                    dates_list = json.loads(t['class_dates'])
                    if not isinstance(dates_list, list):
                        continue
                        
                    for d_str in dates_list:
                        # Filter by date range in python
                        event_date = datetime.strptime(d_str, '%Y-%m-%d').date()
                        
                        if start_date and event_date < pd.to_datetime(start_date).date():
                            continue
                        if end_date and event_date > pd.to_datetime(end_date).date():
                            continue
                            
                        event = Event()
                        event.add('summary', f"🎓 Aula: {t['student_name']}")
                        
                        # Deterministic UID: Needs to be unique per student+date
                        # We use tuition ID + date string
                        event.add('uid', f"aula_{t['id']}_{d_str}@amicando.com.br")
                        
                        event.add('dtstart', event_date)
                        event.add('dtend', event_date + timedelta(days=1))
                        
                        desc = f"Aula referente à mensalidade de {t['month_year']}."
                        event.add('description', desc)
                        event.add('status', 'CONFIRMED')
                        cal.add_component(event)
                        
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"Error exporting classes to ICS: {e}")

    return cal.to_ical()
