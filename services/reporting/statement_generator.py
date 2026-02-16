from fpdf import FPDF
import io
from datetime import datetime
from services.reporting.pdf_core import PDFReport

def generate_student_statement(student_data, items, total_due=None, cancellations=None):
    """
    Generates a PDF statement for a student with centered header and quantity column.
    """
    # Custom PDF class internal to this function to handle specific header logic? 
    # Or reuse PDFReport but override header? 
    # Let's reuse PDFReport but we might need to be careful if PDFReport header is too generic.
    # PDFReport header uses 'Amicando' generic. 
    # The original code had a specific centered header with logo at x=85.
    
    # Let's subclass PDFReport to customize header for this specific report if needed,
    # or just use PDFReport as is. The original code's header was quite good.
    
    class StatementPDF(PDFReport):
        def header(self):
            try:
                # Center the logo
                self.image('logo-amicando-RGB.jpg', x=85, y=10, w=40)
            except:
                pass
            
            # Atelier Data (Full)
            self.set_y(60) # Below logo (Adjusted for overlap)
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 6, 'Amicando Atelier de Cerâmicas', 0, 1, 'C')
            self.set_font('Helvetica', '', 10)
            self.cell(0, 5, 'Instagram: @amicandoatelier | WhatsApp: (54) 99912-1757', 0, 1, 'C')
            self.cell(0, 5, 'Rua Alagoas, 45, sala 103, Bairro Humaitá', 0, 1, 'C')
            self.cell(0, 5, 'Bento Gonçalves, Rio Grande do Sul', 0, 1, 'C')
            
            self.set_y(90) # Move down for title
            self.set_font('Helvetica', 'B', 14)
            self.cell(0, 10, 'Extrato de Conta - Aluno', 0, 1, 'C')
            self.ln(5)
            
    pdf = StatementPDF(f"Extrato - {student_data['name']}")
    
    # Student Info
    pdf.set_font('Helvetica', '', 11)
    pdf.cell(0, 6, f"Aluno: {student_data['name']}", 0, 1)
    if student_data.get('phone'):
        pdf.cell(0, 6, f"Telefone: {student_data['phone']}", 0, 1)
    pdf.cell(0, 6, f"Data do Extrato: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
    pdf.ln(5)
    
    # Table Headers
    # Date (30), Description (85), Qty (15), Value (30), Status (30) - Adjusted width
    w_date = 30
    w_desc = 85
    w_qty = 15
    w_val = 30
    w_status = 30
    
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font('Helvetica', 'B', 10)
    
    pdf.cell(w_date, 8, "Data", 1, 0, 'C', True)
    pdf.cell(w_desc, 8, "Descrição", 1, 0, 'C', True)
    pdf.cell(w_qty, 8, "Qtd", 1, 0, 'C', True)
    pdf.cell(w_val, 8, "Valor (R$)", 1, 0, 'C', True)
    pdf.cell(w_status, 8, "Status", 1, 1, 'C', True)
    
    pdf.set_font('Helvetica', '', 9)
    
    grand_total = 0.0
    
    # Items
    for item in items:
        date_str = item.get('date', '')
        # Robust Date Formatting
        try:
            # Handle pandas Timestamp or string
            import pandas as pd
            if isinstance(date_str, (pd.Timestamp, datetime)):
                 dobj = date_str
            else:
                 # Try to parse string with potential time component
                 # Split by space to get date part if ISO-like
                 clean_str = str(date_str).split(' ')[0]
                 dobj = datetime.strptime(clean_str, '%Y-%m-%d')
            
            date_str = dobj.strftime('%d/%m/%Y')
        except Exception:
             # Fallback: just take first 10 chars if it looks like a date
             if len(str(date_str)) >= 10:
                 date_str = str(date_str)[:10]
             
        desc = item.get('description', '')
        qty = item.get('class_count', 1) 
        if qty is None: qty = 1
        
        # FIX: Use 'value' key as defined in student_service
        val = item.get('value', 0.0)
        status = item.get('status', 'Pendente')
        
        # Color for status
        pdf.set_text_color(0, 0, 0)
        if status == 'Pendente':
             pdf.set_text_color(200, 0, 0)
             grand_total += val
        elif status == 'Pago':
             pdf.set_text_color(0, 128, 0)
             
        pdf.cell(w_date, 7, date_str, 1, 0, 'C')
        pdf.cell(w_desc, 7, desc, 1, 0, 'L')
        pdf.cell(w_qty, 7, str(qty), 1, 0, 'C')
        pdf.cell(w_val, 7, f"{val:.2f}", 1, 0, 'R')
        pdf.cell(w_status, 7, status, 1, 1, 'C')
        
    pdf.set_text_color(0, 0, 0)
    pdf.ln(10)
    
    # Cancellations (if any)
    if cancellations:
        pdf.set_font('Helvetica', 'B', 11)
        pdf.cell(0, 8, "Histórico de Cancelamentos / Faltas", 0, 1)
        
        # Headers
        pdf.set_font('Helvetica', 'B', 9)
        pdf.cell(30, 8, "Data", 1, 0, 'C', True)
        pdf.cell(160, 8, "Motivo", 1, 1, 'C', True)
        
        pdf.set_font('Helvetica', '', 9)
        for c in cancellations:
             c_date = c.get('date', '')
             try:
                 c_date = datetime.strptime(c_date, '%Y-%m-%d').strftime('%d/%m/%y')
             except: pass
             
             pdf.cell(30, 7, c_date, 1, 0, 'C')
             pdf.cell(160, 7, c.get('reason', '-'), 1, 1, 'L')
        pdf.ln(5)
        
    # Total Due
    if total_due is not None:
         # Use passed total due to ensure match with UI
         final_due = total_due
    else:
         final_due = grand_total
         
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(130, 10, "Total Pendente:", 0, 0, 'R')
    pdf.set_text_color(180, 0, 0)
    pdf.cell(60, 10, f"R$ {final_due:.2f}", 0, 1, 'L')
    
    return io.BytesIO(pdf.output(dest='S'))
