# import logging
# import os
# from azure.ai.formrecognizer import DocumentAnalysisClient
# from azure.core.credentials import AzureKeyCredential

# from models.schemas import NormalizedTableCell
# from processors.error_handling import ErrorCode, PipelineError, configure_logger, log_event


# LOGGER = configure_logger(__name__)

# def get_raw_azure_data(pdf_path: str):
#     """Runs Azure Document Intelligence layout analysis and returns raw results."""
#     endpoint = os.getenv("AZURE_ENDPOINT")
#     key = os.getenv("AZURE_KEY")

#     if not endpoint or not key:
#         raise PipelineError(
#             ErrorCode.CONFIGURATION_ERROR,
#             "Azure extraction requires AZURE_ENDPOINT and AZURE_KEY.",
#             recoverable=False,
#             context={"pdf_path": pdf_path},
#         )

#     log_event(LOGGER, logging.INFO, "azure_analysis_started", pdf_path=pdf_path)

#     try:
#         client = DocumentAnalysisClient(
#             endpoint=endpoint,
#             credential=AzureKeyCredential(key)
#         )

#         with open(pdf_path, "rb") as handle:
#             poller = client.begin_analyze_document("prebuilt-layout", document=handle)
#             result = poller.result()

#         log_event(
#             LOGGER,
#             logging.INFO,
#             "azure_analysis_completed",
#             pdf_path=pdf_path,
#             table_count=len(result.tables or []),
#         )
#         return result
#     except FileNotFoundError as exc:
#         error = PipelineError(
#             ErrorCode.FILE_IO_ERROR,
#             "PDF file not found for Azure extraction.",
#             recoverable=False,
#             context={"pdf_path": pdf_path},
#             cause=exc,
#         )
#         log_event(LOGGER, logging.ERROR, "azure_analysis_failed", **error.to_dict())
#         raise error from exc
#     except PipelineError:
#         raise
#     except Exception as exc:
#         error = PipelineError(
#             ErrorCode.EXTERNAL_SERVICE_ERROR,
#             "Azure Document Intelligence request failed.",
#             recoverable=True,
#             context={"pdf_path": pdf_path},
#             cause=exc,
#         )
#         log_event(LOGGER, logging.ERROR, "azure_analysis_failed", **error.to_dict())
#         raise error from exc


# def extract_financial_tables(pdf_path: str):
#     """Normalizes Azure table cell output into row/column/text dictionaries."""
#     try:
#         result = get_raw_azure_data(pdf_path)
#         normalized_cells = []

#         for table in result.tables:
#             for cell in table.cells:
#                 normalized_cells.append(
#                     NormalizedTableCell(
#                         row=cell.row_index,
#                         column=cell.column_index,
#                         text=cell.content or "",
#                     ).model_dump()
#                 )

#         log_event(
#             LOGGER,
#             logging.INFO,
#             "azure_cell_normalization_completed",
#             pdf_path=pdf_path,
#             cells=len(normalized_cells),
#         )
#         return normalized_cells
#     except PipelineError:
#         raise
#     except Exception as exc:
#         error = PipelineError(
#             ErrorCode.NORMALIZATION_ERROR,
#             "Failed to normalize Azure table cells.",
#             recoverable=False,
#             context={"pdf_path": pdf_path},
#             cause=exc,
#         )
#         log_event(LOGGER, logging.ERROR, "azure_cell_normalization_failed", **error.to_dict())
#         raise error from exc
    