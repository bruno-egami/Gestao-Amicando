from fpdf import FPDF
from datetime import datetime
import pandas as pd
import io

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
