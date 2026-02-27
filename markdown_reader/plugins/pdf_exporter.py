from weasyprint import HTML

def export_markdown_to_pdf(html_content: str, output_path: str):
    """ 
    Export rendered HTML content to PDF 

    Args:
        html_content (str): HTML string alredy rendered from Markdown 
        output_path (str): Target PDF file path  
    """
    HTML(string=html_content).write_pdf(output_path)
