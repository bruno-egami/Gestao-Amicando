from fpdf import FPDF
import io
from datetime import datetime
from services.reporting.pdf_core import PDFReport
from utils.logging_config import get_logger

logger = get_logger(__name__)

def generate_quote_pdf(quote_data):
    """
    Generate a PDF for a quote (orçamento).
    quote_data should contain: id, client_name, date_created, date_valid_until, 
                               items (list of dicts with name, qty, price, notes, image),
                               total, discount, notes, delivery, payment
    """
    pdf = PDFReport(f"Orçamento #{quote_data['id']}")
    
    # Client Info
    pdf.add_info_line("Cliente:", quote_data['client_name'])
    pdf.add_info_line("Data:", quote_data['date_created'])
    pdf.add_info_line("Validade:", quote_data['date_valid_until'])
    pdf.ln(5)

    # Global Notes
    if quote_data.get('notes'):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 6, "Observações:", 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 6, quote_data['notes'])
        pdf.ln(5)

    # Items Table Layout
    # Item (80), Qtd (15), Unit (30), Total (30) - Adjusted for A4 Portrait (190mm usable)
    # Let's use custom drawing for items to handle images and notes better than simple table
    
    w_prod = 90
    w_qty = 15
    w_price = 35
    w_sub = 40
    
    # Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 10)
    
    pdf.cell(w_prod, 8, "Item", border=1, align='C', fill=True)
    pdf.cell(w_qty, 8, "Qtd", border=1, align='C', fill=True)
    pdf.cell(w_price, 8, "Unit. (R$)", border=1, align='C', fill=True)
    pdf.cell(w_sub, 8, "Total (R$)", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', '', 10)
    
    for item in quote_data.get('items', []):
        name = item['name']
        qty = item['qty']
        price = item['price']
        total_p = qty * price
        notes = item.get('notes', '')
        image_path = item.get('image') # Path to image
        
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
        
        # 2. Image Height (if exists)
        h_img = 0
        if image_path:
             h_img = 25 # Fixed height for image inside row?
             
        # Total Row Height
        real_h = max(h_text + (h_img + 2 if image_path else 0), 12)
        
        # Draw Product Cell
        pdf.set_xy(x_start, y_start)
        # Text
        pdf.multi_cell(w_prod, 6, display_text, border=0, align='L')
        # Image
        if image_path:
             try:
                 pdf.image(image_path, x=x_start+2, y=y_start+h_text+1, h=20)
             except Exception as e:
                 logger.warning(f"Failed to add image to PDF: {e}")

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
    # pdf.add_totals_row("Total:", f"R$ {quote_data['total']:.2f}", col_widths=None) # Helper not flexible enough
    
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(140, 6, "Total dos Itens:", align='R')
    pdf.cell(40, 6, f"R$ {quote_data['total']:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    if quote_data.get('discount', 0) > 0:
        pdf.cell(140, 6, "Desconto:", align='R')
        pdf.cell(40, 6, f"- R$ {quote_data['discount']:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
        
    final_total = quote_data['total'] - quote_data.get('discount', 0)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(140, 8, "TOTAL FINAL:", align='R')
    pdf.cell(40, 8, f"R$ {final_total:.2f}", align='R', border=1, new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(8)
    
    # Terms
    if quote_data.get('delivery'):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 5, "Prazo de Entrega:", 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, quote_data['delivery'])
        pdf.ln(3)
        
    if quote_data.get('payment'):
        pdf.set_font('Helvetica', 'B', 10)
        pdf.cell(0, 5, "Condições de Pagamento:", 0, 1)
        pdf.set_font('Helvetica', '', 10)
        pdf.multi_cell(0, 5, quote_data['payment'])
    
    # Footer
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, "Este orçamento é válido somente até a data informada.", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", align='C')
    
    return io.BytesIO(pdf.output(dest='S'))
