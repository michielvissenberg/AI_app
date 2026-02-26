from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter
import os

def main():
    # 1. Initialize the converter
    converter = DocumentConverter()
    
    # 2. Point to your financial PDF
    source = "data/testdocument.pdf" 
    
    print(f"--- Analyzing {source} ---")
    
    # 3. Perform the conversion
    result = converter.convert(source)
    print(result)
    
    # 4. Export to Markdown (Best for LLMs and readability)
    content_md = result.document.export_to_markdown()
    
    # 5. Save the output so you can inspect the tables
    with open("data/output_testdocument.md", "w", encoding="utf-8") as f:
        f.write(content_md)
        
    print("--- Extraction Complete! ---")
    print("Check 'output_report.md' to see how the tables look.")

if __name__ == "__main__":
    main()