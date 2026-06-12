import hashlib
from abc import ABC, abstractmethod
from datetime import datetime
from app.utils.logger import logger

class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: bytes) -> dict:
        pass

class PDFInvoiceParser(BaseParser):
    def parse(self, content: bytes) -> dict:
        # Real world apps would employ tools like PyPDF, pdfplumber, or OCR models here
        logger.info("Running PDF specific extraction heuristics.")
        return {
            "vendor_name": "Acme Corp Ltd.",
            "amount": 1250.75,
            "currency": "USD",
            "invoice_date": datetime.utcnow(),
            "line_items": [
                {"description": "Cloud Architecture Consulting", "quantity": 1, "unit_price": 1000.0, "total_price": 1000.0},
                {"description": "Database Migration Support", "quantity": 1, "unit_price": 250.75, "total_price": 250.75}
            ],
            "raw_metadata": {"parser_engine": "HeuristicPDFv1", "confidence_score": 0.94}
        }

class CSVStatementParser(BaseParser):
    def parse(self, content: bytes) -> dict:
        # Real world would wrap around pandas or built-in csv modules
        logger.info("Running CSV structured extraction logic.")
        return {
            "vendor_name": "Global Bank Corp",
            "amount": 5000.00,
            "currency": "EUR", 
            "invoice_date": datetime.utcnow(),
            "line_items": [],
            "raw_metadata": {"parser_engine": "CSVTabularReader", "rows_detected": 12}
        }

class DocumentParserFactory:
    @staticmethod
    def get_parser(filename: str) -> BaseParser:
        ext = filename.split(".")[-1].lower()
        if ext == "pdf":
            return PDFInvoiceParser()
        elif ext == "csv":
            return CSVStatementParser()
        raise ValueError(f"Unsupported file format: {ext}")

def generate_file_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()