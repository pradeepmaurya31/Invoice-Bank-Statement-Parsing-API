import enum
import uuid
from datetime import datetime, UTC
from sqlalchemy import Column, String, Float, DateTime, Enum, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.database.database import Base

class DocumentType(str, enum.Enum):
    PDF = "PDF"
    CSV = "CSV"

class ProcessingStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class Document(Base):
    __tablename__ = "documents"

    # Changed from Integer to UUID primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, index=True, nullable=False)
    document_type = Column(Enum(DocumentType), nullable=False)
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.now(UTC))
    
    # Relationships
    parsed_data = relationship("ParsedFinancialData", uselist=False, back_populates="document", cascade="all, delete-orphan")

class ParsedFinancialData(Base):
    __tablename__ = "parsed_financial_data"

    # Changed to UUID primary key and updated foreign key target type
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), unique=True)
    vendor_name = Column(String, index=True, nullable=True)
    amount = Column(Float, index=True, nullable=True)
    currency = Column(String, index=True, default="USD")
    invoice_date = Column(DateTime(timezone=True), index=True, nullable=True)
    raw_metadata = Column(JSON, nullable=True)
    
    document = relationship("Document", back_populates="parsed_data")
    line_items = relationship("LineItem", back_populates="financial_data", cascade="all, delete-orphan")

class LineItem(Base):
    __tablename__ = "line_items"

    # Changed to UUID primary key and updated foreign key target type
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    financial_data_id = Column(UUID(as_uuid=True), ForeignKey("parsed_financial_data.id"))
    description = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    financial_data = relationship("ParsedFinancialData", back_populates="line_items")