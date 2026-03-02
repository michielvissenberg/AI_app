import os
from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential

from models.schemas import NormalizedTableCell

def get_raw_azure_data(pdf_path: str):
    """
    Connects to Azure Document Intelligence and performs layout analysis on a PDF.

    Args:
        pdf_path (str): The local file path to the PDF document.

    Returns:
        azure.ai.formrecognizer.AnalyzeResult: A heavy object containing 
            all detected text, tables, selection marks, and styles.

    Raises:
        HttpResponseError: If the Azure credentials are invalid or the service is down.
        FileNotFoundError: If the pdf_path does not exist.
    """
    client = DocumentAnalysisClient(
        endpoint=os.getenv("AZURE_ENDPOINT"), 
        credential=AzureKeyCredential(os.getenv("AZURE_KEY"))
    )

    with open(pdf_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout", document=f)
        return poller.result()


def extract_financial_tables(pdf_path: str):
    result = get_raw_azure_data(pdf_path)
    normalized_cells = []

    for table in result.tables:
        for cell in table.cells:
            normalized_cells.append(
                NormalizedTableCell(
                    row=cell.row_index,
                    column=cell.column_index,
                    text=cell.content or "",
                ).model_dump()
            )

    return normalized_cells
    