from fpdf import FPDF
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
        except:
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
        except:
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
