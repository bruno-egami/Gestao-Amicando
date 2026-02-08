"""
Production Service Module
Handles business logic for the Kanban production flow, including stage movement,
material deduction, loss registration, and finalization.
"""
import pandas as pd
import json
import streamlit as st
from datetime import datetime, date, timedelta
import services.product_service as product_service
from utils.logging_config import get_logger, log_exception, log_database_operation

logger = get_logger(__name__)

def get_wip_items(conn, stage=None):
    """
    Fetches WIP items with product, client, and order details.
    """
    query = """
        SELECT w.*, p.name as product_name, p.category as product_category, p.image_paths, c.name as client_name, co.date_due, co.id as real_order_id
        FROM production_wip w
        JOIN products p ON w.product_id = p.id
        LEFT JOIN commission_orders co ON w.order_id = co.id
        LEFT JOIN clients c ON co.client_id = c.id
    """
    params = []
    if stage:
        query += " WHERE w.stage = ?"
        params.append(stage)
    
    # Sort by priority first, then date
    query += " ORDER BY w.priority DESC, w.start_date, co.date_due"
    return pd.read_sql(query, conn, params=params)

def start_production(cursor, product_id, quantity, start_date, notes=None, variant_id=None):
    """
    Initiates a new production card in the 'Fila de Espera' stage.
    """
    history = {
        "Iniciado": datetime.now().strftime("%d/%m %H:%M"), 
        "Fila de Espera": datetime.now().strftime("%d/%m %H:%M")
    }
    history_json = json.dumps(history)
    
    cursor.execute("""
        INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
        VALUES (?, ?, NULL, NULL, 'Fila de Espera', ?, ?, 0, ?, ?)
    """, (int(product_id), int(variant_id) if variant_id else None, int(quantity), start_date, history_json, notes))
    return cursor.lastrowid

def move_stage(cursor, conn, item_id, current_stage, next_stage, qty_move, total_qty, selected_variant_id=None, deduct_glaze=False):
    """
    Advances items through stages with phased material deduction.
    Handles splitting cards if moving partial quantity.
    """
    # Fetch current record
    df_curr = pd.read_sql("SELECT * FROM production_wip WHERE id=?", conn, params=(item_id,))
    if df_curr.empty: 
        raise ValueError("Item não encontrado.")
    curr = df_curr.iloc[0]
    
    # Load existing history
    try:
        history = json.loads(curr['stage_history']) if curr['stage_history'] else {}
    except:
        history = {}
    
    # Add next stage timestamp
    history[next_stage] = datetime.now().strftime("%d/%m %H:%M")
    history_json = json.dumps(history)

    # 1. Automatic Material Deduction
    m_deducted = curr['materials_deducted']
    if next_stage == 'Modelagem' and m_deducted == 0:
        product_service.deduct_production_materials_central(cursor, int(curr['product_id']), qty_move, filter_type='clay')
        m_deducted = 1
        
    # Glaze (if moving to Esmaltação)
    if current_stage == 'Biscoito' and next_stage == 'Esmaltação' and deduct_glaze and selected_variant_id:
        var_data = pd.read_sql("SELECT m.name as mat_name, pv.material_id, pv.material_quantity, m.stock_level FROM product_variants pv LEFT JOIN materials m ON pv.material_id = m.id WHERE pv.id=?", conn, params=(int(selected_variant_id),))
        if not var_data.empty:
            vd = var_data.iloc[0]
            if vd['material_id'] and vd['material_quantity'] > 0:
                d_qty = vd['material_quantity'] * qty_move
                if d_qty > vd['stock_level']:
                    raise ValueError(f"Estoque insuficiente de esmalte: {vd['mat_name']} (Necessário: {d_qty:.3f}, Disponível: {vd['stock_level']:.3f})")
                
                cursor.execute("UPDATE materials SET stock_level = stock_level - ? WHERE id=?", (d_qty, int(vd['material_id'])))
                cursor.execute("INSERT INTO inventory_transactions (date, material_id, quantity, type, notes) VALUES (?, ?, ?, 'SAIDA', ?)", 
                              (date.today().isoformat(), int(vd['material_id']), d_qty, f"Esmaltação Produto ID {curr['product_id']}"))

    # Use provided variant or keep existing
    final_variant_id = selected_variant_id if selected_variant_id else curr['variant_id']

    # 2. Perform Move
    if qty_move == total_qty:
        cursor.execute("""
            UPDATE production_wip 
            SET stage=?, variant_id=?, materials_deducted=?, stage_history=? 
            WHERE id=?
        """, (next_stage, final_variant_id, int(m_deducted), history_json, item_id))
    else:
        # Update current (reduce qty)
        cursor.execute("UPDATE production_wip SET quantity = quantity - ? WHERE id=?", (qty_move, item_id))
        # Insert new item with updated history and stage
        cursor.execute("""
            INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (int(curr['product_id']), final_variant_id, 
              int(curr['order_id']) if pd.notna(curr['order_id']) else None, 
              int(curr['order_item_id']) if pd.notna(curr['order_item_id']) else None, 
              next_stage, qty_move, curr['start_date'], int(m_deducted), history_json, curr['notes']))
    return True

def finalize_production(cursor, item, qty, inc_stock):
    """
    Completes production, updates final stock, handles material deduction for 'others',
    updates orders, and logs history.
    """
    # item is a dict/row from WIP
    item_id = item['id']
    product_id = int(item['product_id'])
    variant_id = int(item['variant_id']) if pd.notna(item['variant_id']) else None
    order_id = int(item['real_order_id']) if pd.notna(item['real_order_id']) else None
    order_item_id = int(item['order_item_id']) if pd.notna(item['order_item_id']) else None

    logger.info(f"Finalizing production: WIP#{item_id}, Product#{product_id}, qty={qty}, inc_stock={inc_stock}")

    # 0. Deduct Remaining Materials (others)
    glaze_mat_id = None
    if variant_id:
        cursor.execute("SELECT material_id FROM product_variants WHERE id=?", (variant_id,))
        glz_info = cursor.fetchone()
        if glz_info: glaze_mat_id = glz_info[0]
    
    product_service.deduct_production_materials_central(
        cursor, product_id, qty, 
        filter_type='others', 
        exclude_ids=[glaze_mat_id] if glaze_mat_id else None
    )

    # 1. Update Order Item (if exists)
    if order_id and order_item_id:
        cursor.execute("UPDATE commission_items SET quantity_produced = quantity_produced + ? WHERE id=?", (qty, order_item_id))
    
    # 2. Increment Stock
    if inc_stock:
        cursor.execute("UPDATE products SET stock_quantity = stock_quantity + ? WHERE id=?", (qty, product_id))
        if variant_id:
            cursor.execute("UPDATE product_variants SET stock_quantity = stock_quantity + ? WHERE id=?", (qty, variant_id))
        logger.debug(f"Stock incremented: Product#{product_id} +{qty}")
            
    # 3. History
    cursor.execute("""
        INSERT INTO production_history (timestamp, product_id, product_name, quantity, order_id, user_id, username)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), product_id, item['product_name'], qty, order_id, None, 'WIP'))
    
    # 4. Check Order Completion
    if order_id:
        cursor.execute("""
            SELECT COUNT(*) FROM commission_items 
            WHERE order_id=? AND quantity_produced < (quantity - quantity_from_stock)
        """, (order_id,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("UPDATE commission_orders SET status='Concluída' WHERE id=?", (order_id,))
            logger.info(f"Order#{order_id} auto-completed (all items produced)")
    
    # 5. Remove/Update WIP
    if qty == item['quantity']:
        cursor.execute("DELETE FROM production_wip WHERE id=?", (item_id,))
    else:
        cursor.execute("UPDATE production_wip SET quantity = quantity - ? WHERE id=?", (qty, item_id))
    
    log_database_operation(logger, "FINALIZE", "production_wip", item_id)
    
    # Clear cache
    get_production_history_stats.clear()
    get_production_log_report.clear()
    
    return True

def register_loss(cursor, item, stage, qty_loss, reason_loss):
    """
    Records a loss, updates WIP, and handles automated replenishment for orders.
    """
    item_id = item['id']
    product_id = int(item['product_id'])
    variant_id = int(item['variant_id']) if pd.notna(item['variant_id']) else None
    order_id = int(item['real_order_id']) if pd.notna(item['real_order_id']) else None
    order_item_id = int(item['order_item_id']) if pd.notna(item['order_item_id']) else None

    # 1. Record Loss
    cursor.execute("""
        INSERT INTO production_losses (timestamp, product_id, variant_id, stage, quantity, reason, order_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (datetime.now().isoformat(), product_id, variant_id, stage, qty_loss, reason_loss, order_id))
    
    # 2. Update Stage History
    try:
        history = json.loads(item['stage_history']) if item.get('stage_history') else {}
    except:
        history = {}
    
    break_key = f"Quebra ({stage})"
    history[break_key] = f"-{qty_loss} pcs | {datetime.now().strftime('%d/%m %H:%M')}"
    history_json = json.dumps(history)
    
    # 3. Update WIP
    if qty_loss == item['quantity']:
        cursor.execute("DELETE FROM production_wip WHERE id=?", (item_id,))
    else:
        cursor.execute("UPDATE production_wip SET quantity = quantity - ?, stage_history=? WHERE id=?", (qty_loss, history_json, item_id))
    
    # 4. Automated Replenishment (for Orders)
    replenished = False
    if order_id:
        rep_history = {
            "Iniciado": datetime.now().strftime("%d/%m %H:%M"), 
            "Fila de Espera (Reposição)": datetime.now().strftime("%d/%m %H:%M")
        }
        rep_history_json = json.dumps(rep_history)
        
        cursor.execute("""
            INSERT INTO production_wip (product_id, variant_id, order_id, order_item_id, stage, quantity, start_date, materials_deducted, stage_history, notes)
            VALUES (?, ?, ?, ?, 'Fila de Espera', ?, ?, 0, ?, ?)
        """, (product_id, variant_id, order_id, order_item_id, qty_loss, date.today().isoformat(), rep_history_json, f"Reposição após quebra em {stage}"))
        replenished = True
        
        replenished = True
        
    # Clear cache
    get_loss_statistics.clear()
        
    return replenished

def update_priority(cursor, item_id, increment):
    """
    Adjusts the priority level of a WIP item.
    """
    cursor.execute("UPDATE production_wip SET priority = priority + ? WHERE id=?", (increment, item_id))
    return True

@st.cache_data(ttl=300, show_spinner=False)
def get_loss_statistics(conn, start_date, end_date):
    """
    Retrieves loss statistics grouped by reason and stage.
    Uses 'production_losses' table.
    """
    query = """
        SELECT stage as 'Estágio', 
               reason as 'Motivo', 
               SUM(quantity) as 'Quantidade',
               p.name as 'Produto'
        FROM production_losses pl
        LEFT JOIN products p ON pl.product_id = p.id
        WHERE DATE(pl.timestamp) BETWEEN ? AND ?
        GROUP BY stage, reason, p.name
    """
    return pd.read_sql(query, conn, params=[start_date, end_date])

@st.cache_data(ttl=300, show_spinner=False)
def get_production_history_stats(conn, days=180):
    """
    Retrieves production history statistics for trend analysis.
    Groups by Month.
    """
    start_date = (date.today() - timedelta(days=days)).isoformat()
    
    query = """
        SELECT strftime('%Y-%m', timestamp) as 'Mes',
               SUM(quantity) as 'Quantidade'
        FROM production_history
        WHERE timestamp >= ?
        GROUP BY strftime('%Y-%m', timestamp)
        ORDER BY Mes ASC
    """
    return pd.read_sql(query, conn, params=[start_date])

@st.cache_data(ttl=60, show_spinner=False)
def get_stage_duration_stats(conn):
    """
    Fetches all active WIP items and calculates duration in current stage.
    Returns a DataFrame with item details and 'days_in_stage'.
    """
    # Fetch active WIP (not Finished)
    query = """
        SELECT w.id, 
               p.name as 'Produto', 
               w.stage as 'Estágio', 
               w.quantity as 'Quantidade', 
               w.stage_history,
               w.start_date
        FROM production_wip w
        JOIN products p ON w.product_id = p.id
        WHERE w.stage != 'Finalizado'
    """
    df = pd.read_sql(query, conn)
    
    if df.empty:
        return pd.DataFrame(columns=['Produto', 'Estágio', 'Quantidade', 'Dias no Estágio', 'Data Entrada'])
        
    results = []
    today = datetime.now()
    
    for _, row in df.iterrows():
        days_in_stage = 0
        entry_date_str = None
        
        # Try to parse history
        try:
            history = json.loads(row['stage_history']) if row['stage_history'] else {}
            
            # Find entry date for current stage
            if row['Estágio'] in history:
                # Format roughly: "dd/mm HH:MM" or "yyyy-mm-dd..." depending on legacy. 
                # The current format used in start_production/move_stage is "%d/%m %H:%M" (current year implied? No, wait)
                # Let's check move_stage implementation: 
                # history[next_stage] = datetime.now().strftime("%d/%m %H:%M") -> This is risky for year transitions!
                # Ideally we should fix the date format in move_stage to ISO, but for now let's handle parsing.
                # If parsed without year, assume current year or adjust if future.
                
                date_str = history[row['Estágio']]
                # Try parsing "%d/%m %H:%M"
                try:
                    dt = datetime.strptime(date_str, "%d/%m %H:%M")
                    # Replace year with current year
                    dt = dt.replace(year=today.year)
                    # If result is in future (e.g. it was Dec 31 and now is Jan 1), subtract a year
                    if dt > today:
                        dt = dt.replace(year=today.year - 1)
                    entry_date_str = dt
                except:
                    # Fallback or different format
                    entry_date_str = today 
            else:
                # Fallback to start_date if Fila/Iniciado or unknown
                # start_date is usually ISO "YYYY-MM-DD" or similar
                try:
                    entry_date_str = datetime.fromisoformat(row['start_date'])
                except (ValueError, TypeError):
                    entry_date_str = today

            if entry_date_str:
                # Calculate fractional days for better precision (e.g. 0.5 days)
                delta = today - entry_date_str
                days_in_stage = round(delta.total_seconds() / 86400, 1)
                
        except (json.JSONDecodeError, KeyError, ValueError, TypeError):
            days_in_stage = 0
            
        results.append({
            'Produto': row['Produto'],
            'Estágio': row['Estágio'],
            'Quantidade': row['Quantidade'],
            'Dias no Estágio': days_in_stage,
            'Data Entrada': entry_date_str.strftime('%d/%m/%Y') if isinstance(entry_date_str, datetime) else str(entry_date_str)
        })
        
    return pd.DataFrame(results)

@st.cache_data(ttl=300, show_spinner=False)
def get_production_log_report(conn, start_date, end_date):
    """
    Retrieves production history logs for report.
    """
    query = """
        SELECT DATE(ph.timestamp) as 'Data', 
               p.name as 'Produto', 
               p.category as 'Categoria',
               SUM(ph.quantity) as 'Quantidade',
               ph.username as 'Usuário'
        FROM production_history ph
        JOIN products p ON ph.product_id = p.id
        WHERE DATE(ph.timestamp) BETWEEN ? AND ?
        GROUP BY DATE(ph.timestamp), ph.product_id, ph.username
        ORDER BY ph.timestamp DESC
    """
    return pd.read_sql(query, conn, params=[start_date, end_date])
