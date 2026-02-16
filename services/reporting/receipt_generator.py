from fpdf import FPDF
import io
from datetime import datetime
from utils.logging_config import get_logger
from services.reporting.pdf_core import PDFReport

logger = get_logger(__name__)

class PDFReceipt(FPDF):
    def header(self):
        try:
            self.image('logo-amicando-RGB.jpg', x=10, y=8, w=33)
        except:
            pass
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Comprovante de Venda', 0, 1, 'C')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, 'Atelier Amicando', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, 'Agradecemos a preferência!', 0, 0, 'C')

def generate_receipt_pdf(data):
    """
    Generates a PDF receipt for a generic sale.
    data format expected:
    {
        "id": str,
        "type": "Venda" or "Encomenda",
        "date": str,
        "date_due": str (optional),
        "client_name": str,
        "items": [ {"name": str, "qty": int, "price": float} ],
        "total": float,
        "discount": float,
        "deposit": float (optional)
    }
    """
    pdf = PDFReceipt()
    pdf.add_page()
    
    # Info
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, f"ID: {data['id']}", 0, 1)
    pdf.cell(0, 6, f"Data: {data['date']}", 0, 1)
    pdf.cell(0, 6, f"Cliente: {data['client_name']}", 0, 1)
    pdf.ln(5)
    
    # Items
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(80, 8, "Item", 1)
    pdf.cell(20, 8, "Qtd", 1, 0, 'C')
    pdf.cell(30, 8, "V. Unit", 1, 0, 'R')
    pdf.cell(30, 8, "Total", 1, 1, 'R')
    
    pdf.set_font('Helvetica', '', 10)
    for item in data['items']:
        pdf.cell(80, 8, item['name'], 1)
        pdf.cell(20, 8, str(item['qty']), 1, 0, 'C')
        pdf.cell(30, 8, f"R$ {item['price']:.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"R$ {item['qty']*item['price']:.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    
    # Totals
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(130, 6, "Total:", 0, 0, 'R')
    pdf.cell(30, 6, f"R$ {data['total']:.2f}", 0, 1, 'R')
    
    if data.get('discount', 0) > 0:
        pdf.cell(130, 6, "Desconto:", 0, 0, 'R')
        pdf.cell(30, 6, f"- R$ {data['discount']:.2f}", 0, 1, 'R')
        
    if data.get('deposit', 0) > 0:
        pdf.cell(130, 6, "Sinal Pago:", 0, 0, 'R')
        pdf.cell(30, 6, f"R$ {data['deposit']:.2f}", 0, 1, 'R')
        
        remaining = data['total'] - data['deposit']
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(130, 6, "Restante:", 0, 0, 'R')
        pdf.cell(30, 6, f"R$ {remaining:.2f}", 0, 1, 'R')
    else:
        # Final Total
        final = data['total'] - data.get('discount', 0)
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(130, 6, "Total Final:", 0, 0, 'R')
        pdf.cell(30, 6, f"R$ {final:.2f}", 0, 1, 'R')

    return io.BytesIO(pdf.output(dest='S'))

def generate_commission_receipt_pdf(order_data):
    """Generates a PDF receipt for a commission order."""
    pdf = PDFReport(f"Recibo de Encomenda #{order_data['id']}", orientation='P')
    
    # Header Info
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Data do Pedido: {order_data['date']}", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Previsão de Entrega: {order_data['date_due']}", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Cliente: {order_data['client_name']}", align='L', new_x="LMARGIN", new_y="NEXT")
    
    # Order Notes (Global)
    if order_data.get('notes'):
        pdf.multi_cell(0, 6, f"Observações: {order_data['notes']}", align='L')
        
    pdf.ln(5)
    
    # Items Table
    # Layout similar to Quote: Product (90), Qty (15), Price (35), Total (40)
    w_prod = 90
    w_qty = 15
    w_price = 35
    w_sub = 40
    
    # Header
    pdf.set_fill_color(51, 51, 51)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 10)
    
    pdf.cell(w_prod, 8, "Item", border=1, align='C', fill=True)
    pdf.cell(w_qty, 8, "Qtd", border=1, align='C', fill=True)
    pdf.cell(w_price, 8, "Unit. (R$)", border=1, align='C', fill=True)
    pdf.cell(w_sub, 8, "Total (R$)", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 10)
    
    for item in order_data.get('items', []):
        name = item['name']
        qty = item['qty']
        price = item['price']
        total_p = qty * price
        notes = item.get('notes', '')
        images = item.get('images', [])
        
        # Prepare Display Text
        display_text = name
        if notes:
            display_text += f"\nObs: {notes}"
            
        # Calculate Row Height
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # 1. Text Height
        pdf.set_xy(x_start, y_start)
        pdf.multi_cell(w_prod, 6, display_text, border=0, align='L')
        h_text = pdf.get_y() - y_start
        
        # 2. Images Height
        h_imgs = 0
        if images:
             h_imgs = 20 # Fixed height for image row
             
        # Total Row Height
        real_h = max(h_text + (h_imgs + 2 if h_imgs else 0), 12)
        
        # Draw Product Cell
        pdf.set_xy(x_start, y_start)
        # Text
        pdf.multi_cell(w_prod, 6, display_text, border=0, align='L')
        # Images
        if images:
            y_imgs = y_start + h_text + 2
            x_img_curr = x_start + 2
            for img_p in images:
                 try:
                     if x_img_curr + 16 > x_start + w_prod: break 
                     pdf.image(img_p, x=x_img_curr, y=y_imgs, w=16, h=16)
                     x_img_curr += 18
                 except Exception as e:
                     logger.warning(f"Failed to load image {img_p} in Receipt PDF: {e}")

        # Draw Border
        pdf.set_xy(x_start, y_start)
        pdf.rect(x_start, y_start, w_prod, real_h)
        
        # Draw Other Cells
        pdf.set_xy(x_start + w_prod, y_start)
        pdf.cell(w_qty, real_h, str(qty), border=1, align='C')
        
        pdf.set_xy(x_start + w_prod + w_qty, y_start)
        pdf.cell(w_price, real_h, f"{price:.2f}", border=1, align='R')
        
        pdf.set_xy(x_start + w_prod + w_qty + w_price, y_start)
        pdf.cell(w_sub, real_h, f"{total_p:.2f}", border=1, align='R')
        
        pdf.set_y(y_start + real_h)
        
    pdf.ln(5)
    
    # Totals
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(140, 10, "Total Final:", align='R')
    pdf.cell(40, 10, f"R$ {order_data['total']:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    # Check if fully paid
    is_paid = order_data.get('status') == 'Entregue' or order_data.get('is_paid')
    
    if order_data.get('deposit'):
        pdf.set_font('Helvetica', '', 10)
        pdf.cell(140, 6, "Sinal Pago:", align='R')
        pdf.cell(40, 6, f"R$ {order_data['deposit']:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
        
    remaining = order_data['total'] - order_data.get('deposit', 0)
    
    if is_paid:
        pdf.set_font('Helvetica', 'B', 12)
        pdf.set_text_color(0, 100, 0) # Green
        pdf.cell(140, 8, "Pagamento Final (Entrega):", align='R')
        pdf.cell(40, 8, f"R$ {remaining:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
        
        pdf.cell(140, 8, "Situação:", align='R')
        pdf.cell(40, 8, "QUITADO", align='R', new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
    else:
        # Standard Remaining
        if order_data.get('deposit'):
            pdf.set_font('Helvetica', 'B', 12)
            pdf.cell(140, 8, "Restante a Pagar:", align='R')
            pdf.cell(40, 8, f"R$ {remaining:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output(dest='S'))
