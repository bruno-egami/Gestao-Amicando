"""
Reports Module (Facade)
This module now delegates to services.reporting to maintain backward compatibility.
All actual logic has been moved to services/reporting/.
"""
from services.reporting.pdf_core import PDFReport, generate_report_pdf
from services.reporting.receipt_generator import PDFReceipt, generate_receipt_pdf, generate_commission_receipt_pdf
from services.reporting.quote_generator import generate_quote_pdf
from services.reporting.statement_generator import generate_student_statement
