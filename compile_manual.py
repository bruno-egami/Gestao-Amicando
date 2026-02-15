
import os
import re
from fpdf import FPDF
from datetime import datetime

class ManualPDF(FPDF):
    def header(self):
        # Logo
        try:
            if os.path.exists('logo-amicando-RGB.jpg'):
                self.image('logo-amicando-RGB.jpg', x=10, y=10, w=30)
            elif os.path.exists('Logo amicando.png'):
                self.image('Logo amicando.png', x=10, y=10, w=30)
        except Exception:
            pass
        
        self.set_font('Helvetica', 'B', 15)
        self.set_xy(45, 15)
        self.cell(0, 10, 'Manual do Usuário - Sistema Amicando', align='L')
        self.set_font('Helvetica', 'I', 9)
        self.set_xy(45, 23)
        self.cell(0, 5, 'Gestão para Atelier de Cerâmica', align='L')
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}} | Gerado em {datetime.now().strftime("%d/%m/%Y")}', align='C')

def clean_text(text):
    """Strip emojis and other non-latin-1 characters for fpdf standard fonts."""
    # Remove emojis and special characters that cause encoding issues in latin-1
    text = re.sub(r'[^\x00-\x7F\xc0-\xff]', '', text)
    # Also remove common markdown symbols that might slip in
    return text.strip()

def compile_manual(md_path, pdf_path):
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return

    pdf = ManualPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Simple split by line
    lines = content.split('\n')
    
    table_buffer = []
    page_w = pdf.w - 20  # 10mm margin on each side
    
    for i, line in enumerate(lines):
        # Always set x back to margin if not in specific indent
        pdf.set_x(10)

        # 1. Handle Tables
        if '|' in line and not line.strip().startswith('-') and not line.strip().startswith('#'):
            if '---' in line: continue
            table_buffer.append([c.strip() for c in line.split('|') if c.strip()])
            continue
        elif table_buffer:
            # Render Table
            pdf.ln(2)
            pdf.set_font('Helvetica', 'B', 9)
            pdf.set_fill_color(240, 240, 240)
            col_w = page_w / len(table_buffer[0])
            for header in table_buffer[0]:
                pdf.cell(col_w, 8, clean_text(header), border=1, fill=True, align='C')
            pdf.ln()
            pdf.set_font('Helvetica', size=8)
            for row in table_buffer[1:]:
                for cell in row:
                    pdf.cell(col_w, 7, clean_text(cell), border=1)
                pdf.ln()
            pdf.ln(2)
            pdf.set_font('Helvetica', size=11)
            table_buffer = []

        # 2. Handle Headers
        if line.startswith('# '):
            pdf.ln(8)
            pdf.set_font('Helvetica', 'B', 16)
            pdf.multi_cell(page_w, 10, clean_text(line[2:]))
            pdf.set_font('Helvetica', size=11)
        elif line.startswith('## '):
            pdf.ln(6)
            pdf.set_font('Helvetica', 'B', 14)
            pdf.multi_cell(page_w, 9, clean_text(line[3:]))
            pdf.set_font('Helvetica', size=11)
        elif line.startswith('### '):
            pdf.ln(4)
            pdf.set_font('Helvetica', 'B', 12)
            pdf.multi_cell(page_w, 8, clean_text(line[4:]))
            pdf.set_font('Helvetica', size=11)
        
        # 3. Handle Lists
        elif line.strip().startswith('- ') or line.strip().startswith('* ') or re.match(r'^\d+\.', line.strip()):
            pdf.set_font('Helvetica', size=11)
            pdf.set_x(15)
            txt = clean_text(line.replace('**', ''))
            pdf.multi_cell(page_w - 5, 6, txt)
        
        # 4. Handle Normal Text
        elif line.strip():
            pdf.set_font('Helvetica', size=11)
            pdf.multi_cell(page_w, 6, clean_text(line.replace('**', '')))
        
        # 5. Empty lines
        else:
            pdf.ln(2)

    pdf.output(pdf_path)
    print(f"Success: Manual compiled to {pdf_path}")

if __name__ == "__main__":
    compile_manual('MANUAL.md', 'Manual_do_usuario.pdf')
