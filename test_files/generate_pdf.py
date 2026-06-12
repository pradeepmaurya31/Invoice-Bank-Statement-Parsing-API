from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_sample_pdf():
    pdf_filename = "invoice_sample1.pdf"
    doc = SimpleDocTemplate(pdf_filename, pagesize=letter)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'InvoiceTitle',
        parent=styles['Heading1'],
        fontSize=24,
        leading=28,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=20
    )
    
    # Document Header / Vendor Info
    story.append(Paragraph("INVOICE", title_style))
    story.append(Paragraph("<b>Vendor:</b> Acme Corp Ltd.", styles['Normal']))
    story.append(Paragraph("<b>Date:</b> June 12, 2026", styles['Normal']))
    story.append(Paragraph("<b>Invoice No:</b> #INV-2026-009A", styles['Normal']))
    story.append(Spacer(1, 20))
    
    # Line Items Table
    data = [
        ["Description", "Quantity", "Unit Price", "Total Price"],
        ["Cloud Architecture Consulting", "1", "$1000.00", "$1000.00"],
        ["Database Migration Support", "1", "$250.75", "$250.75"],
        ["", "", "Total Amount:", "$1250.75"]
    ]
    
    table = Table(data, colWidths=[250, 60, 100, 100])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -2), colors.HexColor("#F7FAFC")),
        ('GRID', (0, 0), (-1, -2), 1, colors.HexColor("#E2E8F0")),
        ('FONTNAME', (2, -1), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (2, -1), (-1, -1), colors.HexColor("#2D3748")),
    ]))
    
    story.append(table)
    doc.build(story)
    print(f"Success! Generated '{pdf_filename}' for testing your FastAPI upload endpoint.")

if __name__ == "__main__":
    generate_sample_pdf()