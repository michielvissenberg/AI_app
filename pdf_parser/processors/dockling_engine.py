from docling.document_converter import DocumentConverter

def extract_financial_tables(pdf_path: str):
    """
    Converts PDF and returns ONLY the tables in Markdown format.
    This strips away all the legal claims and explanations.
    """
    converter = DocumentConverter()
    result = converter.convert(pdf_path)
    
    # We filter the document for table elements only
    tables_markdown = []
    for table in result.document.tables:
        tables_markdown.append(table.export_to_markdown())
        
    return tables_markdown