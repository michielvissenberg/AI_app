from docling.datamodel.base_models import InputFormat
from docling.datamodel.accelerator_options import AcceleratorOptions
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
import pypdfium2 as pdfium

from models.schemas import NormalizedTableCell


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


def _parse_markdown_table(markdown_table: str):
    rows = []
    for line in markdown_table.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if not cells:
            continue

        if all(part.replace(":", "").replace("-", "") == "" for part in cells):
            continue

        rows.append(cells)

    if not rows:
        return []

    if len(rows) > 1:
        rows = rows[1:]

    normalized_cells = []
    for row_index, row in enumerate(rows):
        for column_index, text in enumerate(row):
            normalized_cells.append(
                NormalizedTableCell(row=row_index, column=column_index, text=text)
            )

    return normalized_cells


def _extract_tables_in_chunks(converter: DocumentConverter, pdf_path: str, chunk_size: int = 8):
    page_count = _get_page_count(pdf_path)
    normalized_cells = []
    next_row_offset = 0

    for start_page in range(1, page_count + 1, chunk_size):
        end_page = min(start_page + chunk_size - 1, page_count)
        result = converter.convert(
            pdf_path,
            raises_on_error=False,
            page_range=(start_page, end_page),
        )
        for table in result.document.tables:
            markdown_table = table.export_to_markdown(doc=result.document)
            table_cells = _parse_markdown_table(markdown_table)
            for cell in table_cells:
                normalized_cells.append(
                    NormalizedTableCell(
                        row=cell.row + next_row_offset,
                        column=cell.column,
                        text=cell.text,
                    )
                )

            if table_cells:
                next_row_offset = max(c.row for c in normalized_cells) + 1

    return [cell.model_dump() for cell in normalized_cells]

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
    normalized_cells = _extract_tables_in_chunks(converter, pdf_path, chunk_size=chunk_size)

    if not normalized_cells:
        converter = _build_converter(do_ocr=True, device=device, num_threads=num_threads)
        normalized_cells = _extract_tables_in_chunks(converter, pdf_path, chunk_size=chunk_size)
        
    return normalized_cells