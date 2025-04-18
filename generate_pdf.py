
from weasyprint import HTML

# Your HTML content
resume_html = "<h1>Sample Resume</h1><p>This is a test PDF generation using WeasyPrint.</p>"

# Output PDF path
pdf_path = "resume.pdf"

# Generate PDF using WeasyPrint
HTML(string=resume_html).write_pdf(pdf_path)

print("PDF generated successfully using WeasyPrint!")
