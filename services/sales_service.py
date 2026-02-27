import uuid
import pandas as pd
from datetime import datetime, date
import services.product_service as product_service
import services.order_service as order_service
import audit
from utils.logging_config import get_logger
from database import safe_transaction

logger = get_logger(__name__)

def process_sale_transaction(conn, cart_analysis, client_id, salesperson, payment_method, notes, delivery_days, deposit_val, date_obj=None):
    """
    Process a complete sales transaction, including:
    - Immediate sales (stock deduction)
    - Commission orders (future delivery)
    - Deposits
    - Audit logging
    
    Returns:
        dict: Transaction summary for receipt generation.
    """
    trans_uuid = f"TRX-{datetime.now().strftime('%y%m%d')}-{str(uuid.uuid4())[:4].upper()}"
    order_items = []
    logs = []
    
    # Use provided date/time or defaults to NOW
    if date_obj is None:
        date_obj = datetime.now()
    
    # Calculate delivery date based on today + delivery_days (delivery logic remains based on days)
    # If backdating, the due date might still be relative to 'today' or the backdated date?
    # Usually lead time is from the moment of order. Let's base it on date_obj if it's a date/datetime.
    base_date = date_obj.date() if isinstance(date_obj, datetime) else date_obj
    delivery_date = base_date + pd.Timedelta(days=int(delivery_days))
    
    try:
        with safe_transaction(conn):
            cursor = conn.cursor()
            
            # 1. Process Cart Items
            for ca in cart_analysis:
                it = ca['item']
                q_sell = int(ca['can_sell'])
                q_order = int(ca['must_order'])
                
                # 1.1 Immediate Sale Portion
                if q_sell > 0:
                    disc_pct = it.get('discount_pct', 0)
                    subtotal = it['base_price'] * q_sell
                    disc_sell = subtotal * (disc_pct / 100.0)
                    total_sell = subtotal - disc_sell
                    
                    sale_data = {
                        "date": date_obj, # Pass full datetime/date
                        "product_id": int(it['product_id']),
                        "quantity": q_sell,
                        "total_price": total_sell,
                        "status": "Finalizada",
                        "client_id": client_id,
                        "discount": disc_sell,
                        "payment_method": payment_method,
                        "notes": notes,
                        "salesperson": salesperson,
                        "order_id": trans_uuid,
                        "variant_id": it.get('variant_id')
                    }
                    order_service.create_sale(cursor, sale_data)
                    
                    # Audit
                    audit.log_action(conn, 'CREATE', 'sales', trans_uuid, None, {'audit_msg': 'Partial Sale'}, commit=False)
                    
                    # Deduct Stock
                    deduct_logs = product_service.deduct_stock(cursor, int(it['product_id']), q_sell, variant_id=it.get('variant_id'))
                    logs.extend(deduct_logs)
 
                 # 1.2 Commission Order Portion
                if q_order > 0:
                    order_items.append({
                        'product_id': it['product_id'],
                        'qty': q_order,
                        'unit_price': it['base_price'],
                        'variant_id': it.get('variant_id')
                    })
                    
            # 2. Create Commission Order (if needed)
            new_ord_id = None
            final_notes = notes
            
            if order_items:
                final_notes = f"Gerado via Venda #{trans_uuid}. Obs: {notes}"
                if deposit_val > 0:
                    final_notes += f"\n\nSinal: R$ {deposit_val:.2f}"
 
                order_data = {
                    'client_id': client_id,
                    'date_created': date.today(),
                    'date_due': delivery_date,
                    'status': "Pendente",
                    'total_price': 0, # Calculated by service logic potentially, or 0 here
                    'notes': final_notes,
                    'deposit_amount': deposit_val
                }
                new_ord_id = order_service.create_commission_order(cursor, order_data)
                order_service.add_commission_items(cursor, new_ord_id, order_items)
                
                # 3. Deposit as Sale
                if deposit_val > 0:
                    order_service.create_sale(cursor, {
                        "date": date_obj,
                        "product_id": None,
                        "quantity": 1,
                        "total_price": deposit_val,
                        "status": "Finalizada",
                        "client_id": client_id,
                        "discount": 0,
                        "payment_method": payment_method,
                        "notes": f"Sinal Enc #{new_ord_id}",
                        "salesperson": salesperson,
                        "order_id": f"ENC-{new_ord_id}"
                    })
        
        return {
            "success": True,
            "trans_id": trans_uuid,
            "order_id": new_ord_id,
            "logs": logs
        }
        
    except Exception as e:
        # safe_transaction handles rollback
        logger.error(f"Transaction failed: {e}")
        raise e
