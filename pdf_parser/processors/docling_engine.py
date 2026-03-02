from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
import pypdfium2 as pdfium


def _build_converter(do_ocr: bool, device: str = "auto", num_threads: int = 4) -> DocumentConverter:
    pipeline_options = PdfPipelineOptions(
        do_ocr=do_ocr,
        force_backend_text=not do_ocr,
        ocr_batch_size=1,
        layout_batch_size=1,
        table_batch_size=1,
        accelerator_options=AcceleratorOptions(device=device, num_threads=num_threads),
    )

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        }
    )


def _get_page_count(pdf_path: str) -> int:
    document = pdfium.PdfDocument(pdf_path)
    return len(document)


def _extract_tables_in_chunks(converter: DocumentConverter, pdf_path: str, chunk_size: int = 8):
    page_count = _get_page_count(pdf_path)
    tables_markdown = []

    for start_page in range(1, page_count + 1, chunk_size):
        end_page = min(start_page + chunk_size - 1, page_count)
        result = converter.convert(
            pdf_path,
            raises_on_error=False,
            page_range=(start_page, end_page),
        )
        for table in result.document.tables:
            tables_markdown.append(table.export_to_markdown(doc=result.document))

    return tables_markdown

def extract_financial_tables(
    pdf_path: str,
    device: str = "auto",
    chunk_size: int = 8,
    num_threads: int = 4,
):
    """
    Converts PDF and returns ONLY the tables in Markdown format.
    This strips away all the legal claims and explanations.
    """
    converter = _build_converter(do_ocr=False, device=device, num_threads=num_threads)
    tables_markdown = _extract_tables_in_chunks(converter, pdf_path, chunk_size=chunk_size)

    if not tables_markdown:
        converter = _build_converter(do_ocr=True, device=device, num_threads=num_threads)
        tables_markdown = _extract_tables_in_chunks(converter, pdf_path, chunk_size=chunk_size)
        
    return tables_markdown