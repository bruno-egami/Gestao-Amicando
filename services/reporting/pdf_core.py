from fpdf import FPDF
import io
from datetime import datetime
import pandas as pd
from utils.logging_config import get_logger

logger = get_logger(__name__)

class PDFReport(FPDF):
    """Generic PDF report with tables for stock, sales, expenses, etc."""
    def __init__(self, title, orientation='P'):
        super().__init__(orientation=orientation)
        self.report_title = title
        self.add_page()
        
    def header(self):
        # Logo (Try multiple formats)
        try:
            # self.image('Logo amicando.png', x=10, y=8, w=33)
            # Use smaller logo or text if not found
             if self.orientation == 'P':
                 self.set_font('Helvetica', 'B', 15)
                 self.cell(0, 10, 'Atelier Amicando', 0, 1, 'C')
             else:
                 self.set_font('Helvetica', 'B', 15)
                 self.cell(0, 10, 'Atelier Amicando', 0, 1, 'C')
        except Exception:
            pass
            
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, self.report_title, 0, 1, 'C')
        self.ln(5)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()} | Gerado em {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'C')

    def add_info_line(self, label, value):
        self.set_font('Helvetica', 'B', 10)
        self.cell(40, 6, label, 0, 0, 'L')
        self.set_font('Helvetica', '', 10)
        self.cell(0, 6, str(value), 0, 1, 'L')

    def add_table(self, headers, data, col_widths=None):
        # Calculate column widths if not provided
        page_width = self.w - 20
        if not col_widths:
            col_widths = [page_width / len(headers)] * len(headers)
            
        # Header
        self.set_fill_color(200, 200, 200)
        self.set_font('Helvetica', 'B', 10)
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, 1, 0, 'C', True)
        self.ln()
        
        # Data
        self.set_font('Helvetica', '', 9)
        for row in data:
            for i, item in enumerate(row):
                self.cell(col_widths[i], 6, str(item), 1, 0, 'C')
            self.ln()
            
    def add_totals_row(self, label, value, col_widths=None):
        page_width = self.w - 20
        if not col_widths:
             # Default assumption
             return 
             
        total_width = sum(col_widths)
        label_width = sum(col_widths[:-1])
        value_width = col_widths[-1]
        
        self.set_font('Helvetica', 'B', 10)
        self.cell(label_width, 7, label, 1, 0, 'R')
        self.cell(value_width, 7, str(value), 1, 1, 'C')

    def add_chart(self, image_bytes, width=180):
        try:
             import tempfile
             import os
             
             with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                 tmp.write(image_bytes)
                 tmp_path = tmp.name
                 
             self.image(tmp_path, x=10, w=width)
             self.ln(10)
             os.remove(tmp_path)
        except Exception as e:
            logger.error(f"Error adding chart to PDF: {e}")

def generate_report_pdf(title, info_lines, headers, data, col_widths=None, totals=None, orientation='P', chart_image=None):
    """
    Generate a generic report PDF.
    
    Args:
        title: Report title
        info_lines: dict of {label: value} for header info
        headers: list of column headers
        data: list of rows (each row is a list)
        col_widths: list of widths (optional)
        totals: tuple (label, value) for a totals row (optional)
        orientation: 'P' or 'L'
        chart_image: optional bytes of chart image to include
    
    Returns:
        BytesIO with PDF content
    """
    pdf = PDFReport(title, orientation)
    
    if info_lines:
        for k, v in info_lines.items():
            pdf.add_info_line(k, v)
        pdf.ln(5)
        
    if chart_image:
        pdf.add_chart(chart_image, width=280 if orientation=='L' else 190)
        
    if headers and data:
        pdf.add_table(headers, data, col_widths)
        
    if totals and col_widths:
        pdf.add_totals_row(totals[0], totals[1], col_widths)
        
    return io.BytesIO(pdf.output(dest='S'))
