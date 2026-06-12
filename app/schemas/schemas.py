from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.models.models import DocumentType, ProcessingStatus

# --- Line Items ---
class LineItemBase(BaseModel):
    description: str
    quantity: int = 1
    unit_price: float
    total_price: float

class LineItemResponse(LineItemBase):
    id: int
    class Config:
        from_attributes = True

# --- Financial Core Data ---
class ParsedDataResponse(BaseModel):
    id: int
    vendor_name: Optional[str]
    amount: Optional[float]
    currency: Optional[str]
    invoice_date: Optional[datetime]
    line_items: List[LineItemResponse] = []
    raw_metadata: Optional[dict] = None

    class Config:
        from_attributes = True

class ParsedDataUpdate(BaseModel):
    vendor_name: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    invoice_date: Optional[datetime] = None

# --- Document Base ---
class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_hash: str
    document_type: DocumentType
    status: ProcessingStatus
    error_message: Optional[str]
    created_at: datetime
    parsed_data: Optional[ParsedDataResponse] = None

    class Config:
        from_attributes = True