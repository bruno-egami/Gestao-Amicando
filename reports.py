from fpdf import FPDF
import io
from datetime import datetime
import pandas as pd
import io

class PDFReport(FPDF):
    """Generic PDF report with tables for stock, sales, expenses, etc."""
    
    def __init__(self, title, orientation='P'):
        super().__init__(orientation=orientation)
        self.report_title = title
        self.add_page()
        self.set_auto_page_break(auto=True, margin=15)
        
    def header(self):
        # Logo
        try:
            self.image('logo-amicando-RGB.jpg', x=10, y=10, w=30)
        except (FileNotFoundError, RuntimeError):
            pass
        
        # Title
        self.set_font('Helvetica', 'B', 16)
        self.set_xy(45, 15)
        self.cell(0, 10, self.report_title, align='L')
        
        # Subtitle - Company name
        self.set_font('Helvetica', '', 10)
        self.set_xy(45, 25)
        self.cell(0, 5, 'Amicando Atelier de Cerâmicas', align='L')
        
        self.ln(25)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} | Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')
    
    def add_info_line(self, label, value):
        """Add a label: value line"""
        self.set_font('Helvetica', 'B', 10)
        self.cell(40, 6, f"{label}:", align='L')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, str(value), align='L', new_x="LMARGIN", new_y="NEXT")
    
    def add_table(self, headers, data, col_widths=None):
        """
        Add a formatted table.
        headers: list of column names
        data: list of lists (rows)
        col_widths: optional list of column widths
        """
        if col_widths is None:
            # Auto-calculate widths based on page width
            available_width = self.w - 20  # 10mm margins each side
            col_widths = [available_width / len(headers)] * len(headers)
        
        # Header row
        self.set_fill_color(52, 73, 94)  # Dark blue-gray
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 9)
        
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, str(header), border=1, fill=True, align='C')
        self.ln()
        
        # Data rows
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', '', 9)
        
        fill = False
        for row in data:
            if fill:
                self.set_fill_color(245, 245, 245)
            else:
                self.set_fill_color(255, 255, 255)
            
            for i, cell in enumerate(row):
                # Right-align numbers, left-align text
                align = 'R' if isinstance(cell, (int, float)) or (isinstance(cell, str) and cell.replace('.','').replace(',','').replace('-','').isdigit()) else 'L'
                cell_text = str(cell)[:30]  # Truncate long text
                self.cell(col_widths[i], 7, cell_text, border=1, fill=True, align=align)
            self.ln()
            fill = not fill
    
    def add_totals_row(self, label, value, col_widths=None):
        """Add a totals row spanning the table"""
        self.set_font('Helvetica', 'B', 10)
        self.set_fill_color(230, 230, 230)
        
        total_width = sum(col_widths) if col_widths else self.w - 20
        label_width = total_width * 0.7
        value_width = total_width * 0.3
        
        self.cell(label_width, 8, label, border=1, fill=True, align='R')
        self.cell(value_width, 8, str(value), border=1, fill=True, align='R')
        self.ln()
    
    def add_chart(self, image_bytes, width=180):
        """Add a chart image to the PDF"""
        import tempfile
        import os
        
        # Save bytes to temp file (fpdf needs file path)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(image_bytes)
            tmp_path = tmp.name
        
        try:
            # Center the image
            x = (self.w - width) / 2
            self.image(tmp_path, x=x, w=width)
            self.ln(10)
        finally:
            # Clean up temp file
            os.unlink(tmp_path)

def generate_report_pdf(title, info_lines, headers, data, col_widths=None, totals=None, orientation='P', chart_image=None):
    """
    Generate a generic report PDF.
    
    Args:
        title: Report title
        info_lines: dict of {label: value} for header info
        headers: list of column headers
        data: list of rows (each row is a list)
        col_widths: optional column widths
        totals: optional list of (label, value) tuples for totals section
        orientation: 'P' for portrait, 'L' for landscape
        chart_image: optional bytes of chart image to include
    
    Returns:
        BytesIO with PDF content
    """
    pdf = PDFReport(title, orientation=orientation)
    
    # Info lines (period, filters, etc.)
    if info_lines:
        for label, value in info_lines.items():
            pdf.add_info_line(label, value)
        pdf.ln(5)
    
    # Chart image (if provided)
    if chart_image:
        chart_width = 270 if orientation == 'L' else 180
        pdf.add_chart(chart_image, width=chart_width)
    
    # Main table
    if headers and data:
        pdf.add_table(headers, data, col_widths)
    
    # Totals
    if totals:
        pdf.ln(3)
        for label, value in totals:
            pdf.add_totals_row(label, value, col_widths)
    
    return io.BytesIO(pdf.output(dest='S'))


class PDFReceipt(FPDF):
    def header(self):
        # Logo - standard position, width optimized for header
        # Using A4 width approx 210mm. 
        # Logo at top center? "Centralizado"
        try:
            # y=10, w=40 (approx 4cm wide), centered
            # x = (210 - 40) / 2 = 85
            self.image('logo-amicando-RGB.jpg', x=85, y=10, w=40)
            self.set_y(55) # Move cursor down explicitly below logo (10 + ~40 height + margin)
        except (FileNotFoundError, RuntimeError):
             # Fallback if image not found
             self.set_font('Helvetica', 'B', 16)
             self.cell(0, 10, 'Atelier Amicando', new_x="LMARGIN", new_y="NEXT", align='C')
        
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 8, 'Amicando Atelier de Cerâmicas', new_x="LMARGIN", new_y="NEXT", align='C')
        
        self.set_font('Helvetica', '', 10)
        self.cell(0, 5, 'Instagram: @amicandoatelier  |  WhatsApp: (54) 99912-1757', new_x="LMARGIN", new_y="NEXT", align='C')
        self.cell(0, 5, 'Rua Alagoas, 45, sala 103, Bairro Humaitá', new_x="LMARGIN", new_y="NEXT", align='C')
        self.cell(0, 5, 'Bento Gonçalves, Rio Grande do Sul', new_x="LMARGIN", new_y="NEXT", align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

def generate_receipt_pdf(data):
    """
    Generates a PDF receipt.
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
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Transaction Info
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, f"Recibo de {data.get('type', 'Venda')} #{data.get('id', '-')}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"Data do Pedido: {data.get('date', '-')}", new_x="LMARGIN", new_y="NEXT")
    if data.get('date_due'):
        pdf.cell(0, 6, f"Previsão de Entrega: {data.get('date_due')}", new_x="LMARGIN", new_y="NEXT")
    
    pdf.cell(0, 6, f"Cliente: {data.get('client_name', 'Consumidor Final')}", new_x="LMARGIN", new_y="NEXT")
    
    # Extra Details
    if data.get('salesperson'):
        pdf.cell(0, 6, f"Vendedor(a): {data.get('salesperson')}", new_x="LMARGIN", new_y="NEXT")
    if data.get('payment_method'):
        pdf.cell(0, 6, f"Pagamento: {data.get('payment_method')}", new_x="LMARGIN", new_y="NEXT")
    if data.get('notes'):
        pdf.multi_cell(0, 6, f"Observações: {data.get('notes')}")
        
    pdf.ln(5)
    
    # Items Table Header
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(100, 8, "Item", border=1, fill=True)
    pdf.cell(20, 8, "Qtd", border=1, fill=True, align='C')
    pdf.cell(35, 8, "Unit. (R$)", border=1, fill=True, align='R')
    pdf.cell(35, 8, "Total (R$)", border=1, fill=True, align='R', new_x="LMARGIN", new_y="NEXT")
    
    # Items List
    pdf.set_font('Helvetica', '', 10)
    total_calc = 0
    for item in data.get('items', []):
        name = item.get('name', 'Item')[:45] # Truncate if too long
        qty = item.get('qty', 0)
        price = float(item.get('price', 0))
        sub = qty * price
        total_calc += sub
        
        pdf.cell(100, 8, name, border=1)
        pdf.cell(20, 8, str(qty), border=1, align='C')
        pdf.cell(35, 8, f"{price:.2f}", border=1, align='R')
        pdf.cell(35, 8, f"{sub:.2f}", border=1, align='R', new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Totals
    # Allow passing pre-calculated totals or use calculated
    final_total = float(data.get('total', total_calc))
    discount = float(data.get('discount', 0))
    deposit = float(data.get('deposit', 0))
    
    pdf.set_font('Helvetica', '', 10)
    
    # Subtotal (if discount exists)
    if discount > 0:
         pdf.cell(155, 6, "Subtotal:", align='R')
         pdf.cell(35, 6, f"R$ {total_calc:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
         pdf.cell(155, 6, "Desconto:", align='R')
         pdf.cell(35, 6, f"- R$ {discount:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    if deposit > 0:
         pdf.cell(155, 6, "Sinal Pago:", align='R')
         pdf.cell(35, 6, f"- R$ {deposit:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
         
         remaining = final_total - deposit
         pdf.set_font('Helvetica', 'B', 12)
         pdf.cell(155, 8, "Restante a Pagar:", align='R')
         pdf.cell(35, 8, f"R$ {remaining:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")

    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(155, 10, "Total Final:", align='R')
    pdf.cell(35, 10, f"R$ {final_total:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    return io.BytesIO(pdf.output(dest='S'))


def generate_quote_pdf(quote_data):
    """
    Generate a PDF for a quote (orçamento).
    quote_data should contain: id, client_name, date_created, date_valid_until, 
                               items (list of dicts with name, qty, price, notes, image),
                               total, discount, notes, delivery, payment
    """
    class PDF(FPDF):
        def header(self):
            # Logo centered
            try:
                self.image('logo-amicando-RGB.jpg', x=85, y=10, w=40)
            except (FileNotFoundError, RuntimeError):
                pass
            
            self.set_y(55) # Below logo
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 6, "Amicando Atelier de Cerâmicas", align='C', new_x="LMARGIN", new_y="NEXT")
            
            self.set_font('Helvetica', '', 9)
            self.cell(0, 5, "Instagram: @amicandoatelier | WhatsApp: (54) 99912-1757", align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, "Rua Alagoas, 45, sala 103, Bairro Humaitá", align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, "Bento Gonçalves, Rio Grande do Sul", align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}', align='C')

    pdf = PDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Generate Formatted ID: ORC-YYMMDD-ID
    try:
        dt_parts = quote_data.get('date_created', '').split('/')
        if len(dt_parts) == 3:
            yymmdd = f"{dt_parts[2][-2:]}{dt_parts[1]}{dt_parts[0]}"
        else:
            yymmdd = "000000"
    except:
        yymmdd = "000000"
        
    formatted_id = f"ORC-{yymmdd}-{quote_data.get('id')}"
    
    # Title Left Aligned
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 6, f"ORÇAMENTO #{formatted_id}", align='L', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    
    # Client info
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(25, 6, "Cliente:", align='L')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, quote_data.get('client_name', 'N/A'), align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(25, 6, "Data:", align='L')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, quote_data.get('date_created', 'N/A'), align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(25, 6, "Válido até:", align='L')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, quote_data.get('date_valid_until', 'N/A'), align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Items table header
    pdf.set_fill_color(51, 51, 51)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 10)
    
    # Widths (Merged Img into Prod)
    # w_img was 20, w_prod was 70. Now w_prod = 90.
    w_prod = 90
    w_qty = 15
    w_price = 35
    w_sub = 40
    
    # pdf.cell(w_img, 8, "Img", border=1, align='C', fill=True) # REMOVED
    pdf.cell(w_prod, 8, "Produto", border=1, align='C', fill=True)
    pdf.cell(w_qty, 8, "Qtd", border=1, align='C', fill=True)
    pdf.cell(w_price, 8, "Unit.", border=1, align='C', fill=True)
    pdf.cell(w_sub, 8, "Subtotal", border=1, align='C', fill=True, new_x="LMARGIN", new_y="NEXT")
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 10)
    
    # Item Loop
    total = 0
    for item in quote_data.get('items', []):
        name = item['name']
        notes = item.get('notes', '')
        qty = item['qty']
        price = item['price'] or 0.0
        subtotal = qty * price
        total += subtotal
        
        # Image Handling (All images)
        images = item.get('images', [])
        if not images and item.get('image'):
            images = [item.get('image')]
        
        # Text preparation
        # ID #123 - Name
        display_text = f"ID #{item.get('id', '?')} - {name}"
        if notes:
            display_text += f"\nObs: {notes}"
        
        # Calculate Row Height
        x_start = pdf.get_x()
        y_start = pdf.get_y()
        
        # 1. Text Height
        pdf.set_xy(x_start, y_start) # Start at left (no w_img offset)
        pdf.multi_cell(w_prod, 6, display_text, border=0, align='L') # No border initially
        y_end_text = pdf.get_y()
        h_text = y_end_text - y_start
        
        # 2. Images Height
        h_imgs = 0
        if images:
             h_imgs = 20 # Fixed height for image row
             
        # Total Row Height (Text + Padding + Images + Padding)
        real_h = max(h_text + (h_imgs + 2 if h_imgs else 0), 12) # Min 12mm
        
        # Re-set XY to start of row
        pdf.set_xy(x_start, y_start)
        
        # 3. Draw Product Cell (Border handled by Rect later?)
        # Draw Text
        pdf.multi_cell(w_prod, 6, display_text, border=0, align='L')
        
        # Draw Images
        if images:
            y_imgs = y_start + h_text + 2
            x_img_curr = x_start + 2
            for img_p in images: # Show all images side-by-side
                 try:
                     # Fit 16x16
                     # Check if it fits in width? w_prod=90. 5 images = 85mm. 
                     if x_img_curr + 16 > x_start + w_prod: break 
                     
                     pdf.image(img_p, x=x_img_curr, y=y_imgs, w=16, h=16)
                     x_img_curr += 18 # 16 + 2 gap
                 except: pass

        # Draw Border around Product Cell
        pdf.set_xy(x_start, y_start)
        pdf.rect(x_start, y_start, w_prod, real_h)
        
        # 4. Draw other cells (Qty, Price, Sub)
        pdf.set_xy(x_start + w_prod, y_start)
        pdf.cell(w_qty, real_h, str(qty), border=1, align='C')
        
        pdf.set_xy(x_start + w_prod + w_qty, y_start)
        pdf.cell(w_price, real_h, f"R$ {price:.2f}", border=1, align='R')
        
        pdf.set_xy(x_start + w_prod + w_qty + w_price, y_start)
        pdf.cell(w_sub, real_h, f"R$ {subtotal:.2f}", border=1, align='R')
        
        pdf.set_y(y_start + real_h) # Move to next row start
        
    pdf.ln(5)
    
    # Final Total (Clean Layout)
    pdf.set_font('Helvetica', 'B', 12)
    pdf.set_x(10) # Margin
    pdf.cell(140, 10, "Total Final:", align='R')
    pdf.cell(40, 10, f"R$ {total:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    # Delivery and Payment Terms
    has_terms = quote_data.get('delivery') or quote_data.get('payment')
    if has_terms:
         pdf.ln(5)
         pdf.set_font('Helvetica', 'B', 10)
         if quote_data.get('delivery'):
             pdf.cell(35, 6, "Prazo de Entrega:", align='L')
             pdf.set_font('Helvetica', '', 10)
             pdf.cell(0, 6, quote_data['delivery'], align='L', new_x="LMARGIN", new_y="NEXT")
         
         pdf.set_font('Helvetica', 'B', 10)
         if quote_data.get('payment'):
             pdf.cell(45, 6, "Condições de Pagamento:", align='L')
             pdf.set_font('Helvetica', '', 10)
             pdf.cell(0, 6, quote_data['payment'].replace('sinal', 'entrada'), align='L', new_x="LMARGIN", new_y="NEXT")
    
    # General Notes
    notes = quote_data.get('notes')
    if notes:
        pdf.ln(5)
        pdf.set_font('Helvetica', 'I', 10)
        pdf.multi_cell(0, 5, f"Observações Gerais:\n{notes}")
        
    # Footer
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 8)
    pdf.cell(0, 5, "Este orçamento é válido somente até a data informada.", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 5, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}", align='C')
    
    return io.BytesIO(pdf.output(dest='S'))

def generate_receipt_pdf(order_data):
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
                 except: pass

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
    # Totals
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(140, 10, "Total Final:", align='R')
    pdf.cell(40, 10, f"R$ {order_data['total']:.2f}", align='R', new_x="LMARGIN", new_y="NEXT")
    
    # Check if fully paid (Status Entregue or explicit flag)
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

def generate_student_statement(student_data, items, total_due=None):
    """
    Generates a PDF statement for a student with centered header and quantity column.
    """
    class PDF(FPDF):
        def header(self):
            # Centered Header Standard
            try:
                self.image('logo-amicando-RGB.jpg', x=85, y=10, w=40)
            except (FileNotFoundError, RuntimeError):
                pass
            
            self.set_y(55) # Below logo
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 6, "Amicando Atelier de Cerâmicas", align='C', new_x="LMARGIN", new_y="NEXT")
            
            self.set_font('Helvetica', '', 9)
            self.cell(0, 5, "Instagram: @amicandoatelier | WhatsApp: (54) 99912-1757", align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, "Rua Alagoas, 45, sala 103, Bairro Humaitá", align='C', new_x="LMARGIN", new_y="NEXT")
            self.cell(0, 5, "Bento Gonçalves, Rio Grande do Sul", align='C', new_x="LMARGIN", new_y="NEXT")
            self.ln(10)

        def footer(self):
            self.set_y(-15)
            self.set_font('Helvetica', 'I', 8)
            self.cell(0, 10, f'Página {self.page_no()}/{{nb}} - Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', align='C')

    pdf = PDF(orientation='P')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Title
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, "EXTRATO DE AULAS E CONSUMO", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # Student Info
    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(20, 6, "Aluno(a):", align='L')
    pdf.set_font('Helvetica', '', 10)
    pdf.cell(0, 6, f"{student_data.get('name')}", align='L', new_x="LMARGIN", new_y="NEXT")
    
    if student_data.get('month'):
         pdf.set_font('Helvetica', 'B', 10)
         pdf.cell(25, 6, "Referência:", align='L')
         pdf.set_font('Helvetica', '', 10)
         pdf.cell(0, 6, f"{student_data.get('month')}", align='L', new_x="LMARGIN", new_y="NEXT")
    
    pdf.ln(5)
    
    # Table Header
    # Cols: Data (20), Descrição (60), Qtd (15), Valor Original (25), Pago (25), Restante (25), Status (20)
    # Total Width = 190 (A4 is 210, margins 10+10)
    headers = ["Data", "Descrição", "Qtd", "Total", "Pago", "Restante", "Status"]
    col_widths = [20, 60, 15, 25, 25, 25, 20]
    
    pdf.set_fill_color(51, 51, 51)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Helvetica', 'B', 8)
    
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, h, border=1, fill=True, align='C')
    pdf.ln()
    
    # Table Data
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Helvetica', '', 8)
    
    fill = False
    
    calc_total_due = 0.0
    
    for item in items:
        # Determine Fill
        pdf.set_fill_color(245, 245, 245) if fill else pdf.set_fill_color(255, 255, 255)
        
        qty_val = item.get('quantity', 1)
        # Handle values safely
        try: val = float(item.get('value', 0) or 0)
        except: val = 0.0
        
        try: paid = float(item.get('paid', 0) or 0)
        except: paid = 0.0
        
        # If item is marked 'Pago' but paid is 0, assume it was fully paid before tracking
        status = str(item.get('status', 'Pendente'))
        if status == 'Pago':
             # If paid is 0 but status is 'Pago', we assume full payment unless paid is explicitly tracked
             if paid == 0: paid = val
        
        remaining = val - paid
        if remaining < 0: remaining = 0
        
        if status == 'Pendente':
             calc_total_due += remaining
        
        # Format Qty
        qty_str = f"{int(qty_val)}" if qty_val == int(qty_val) else f"{qty_val:.2f}"
        
        row_data = [
            str(item.get('date', '-')),
            str(item.get('description', '-'))[:35], # truncated
            qty_str,
            f"{val:.2f}",
            f"{paid:.2f}",
            f"{remaining:.2f}",
            status
        ]
        
        for i, dh in enumerate(row_data):
            align = 'R' if i in [2, 3, 4, 5] else 'L' # Numbers right aligned
            if i == 6: align = 'C' # Status centered
            pdf.cell(col_widths[i], 7, dh, border=1, fill=fill, align=align)
        
        pdf.ln()
        fill = not fill
    
    # Totals Section
    pdf.ln(5)
    
    # Final Total to Pay
    # Use total_due if provided, else calculated
    final_total = total_due if total_due is not None else calc_total_due
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(130, 10, "Total a Pagar:", align='R')
    pdf.cell(60, 10, f"R$ {float(final_total):.2f}", align='R', border=1)
    
    return io.BytesIO(pdf.output(dest='S'))
