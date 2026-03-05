#!/usr/bin/env python3
"""
Create a simple test PDF for testing PDF analyzer
"""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from pathlib import Path

def create_test_pdf(output_path="test_presentation.pdf"):
    """Create a simple test PDF with multiple pages"""
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Page 1: Title slide
    c.setFont("Helvetica-Bold", 24)
    c.drawString(100, height - 200, "Test Presentation")
    c.setFont("Helvetica", 16)
    c.drawString(100, height - 250, "Page 1: Introduction")
    c.drawString(100, height - 300, "This is a test PDF for PDF analyzer tool.")
    c.showPage()
    
    # Page 2: Content slide
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, height - 150, "Page 2: Main Content")
    c.setFont("Helvetica", 14)
    c.drawString(100, height - 200, "• Feature 1: PDF to image conversion")
    c.drawString(100, height - 230, "• Feature 2: Multimodal LLM analysis")
    c.drawString(100, height - 260, "• Feature 3: Page-by-page analysis")
    c.showPage()
    
    # Page 3: Conclusion slide
    c.setFont("Helvetica-Bold", 20)
    c.drawString(100, height - 150, "Page 3: Conclusion")
    c.setFont("Helvetica", 14)
    c.drawString(100, height - 200, "This PDF contains 3 pages.")
    c.drawString(100, height - 230, "It can be used to test the PDF analyzer.")
    c.showPage()
    
    c.save()
    print(f"Created test PDF: {output_path}")
    return output_path

if __name__ == "__main__":
    output_dir = Path(__file__).parent.parent / "output"
    output_dir.mkdir(exist_ok=True)
    pdf_path = output_dir / "test_presentation.pdf"
    create_test_pdf(str(pdf_path))
