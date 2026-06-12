from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime
from app.configs.config import settings
from app.database.database import get_db, Base, engine
from app.models.models import Document, ParsedFinancialData, LineItem, DocumentType, ProcessingStatus
from app.schemas.schemas import DocumentResponse, ParsedDataUpdate
from app.manager.parser import DocumentParserFactory, generate_file_hash
from app.utils.logger import logger

parser_router = APIRouter(prefix="/documents")

# --- 1. UPLOAD FILE ROUTE ---
@parser_router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    # Validate extension type
    extension = file.filename.split(".")[-1].lower()
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file format. Allowed: {settings.ALLOWED_EXTENSIONS}")
    
    content = await file.read()
    
    # Validate file size limits
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File volume size exceeds safety parameters limit.")
    
    # De-duplication matching
    file_hash = generate_file_hash(content)
    existing_doc_query = await db.execute(select(Document).where(Document.file_hash == file_hash))
    if existing_doc_query.scalars().first():
        raise HTTPException(status_code=409, detail="Duplicate identity footprint: This file has already been ingested.")

    # Instantiate preliminary pipeline record
    doc_type = DocumentType.PDF if extension == "pdf" else DocumentType.CSV
    document = Document(filename=file.filename, file_hash=file_hash, document_type=doc_type, status=ProcessingStatus.PENDING)
    db.add(document)
    await db.flush()

    try:
        # Dynamic strategy engine extraction 
        parser = DocumentParserFactory.get_parser(file.filename)
        parsed_results = parser.parse(content)
        
        # Populate operational entities
        financial_data = ParsedFinancialData(
            document_id=document.id,
            vendor_name=parsed_results.get("vendor_name"),
            amount=parsed_results.get("amount"),
            currency=parsed_results.get("currency"),
            invoice_date=parsed_results.get("invoice_date"),
            raw_metadata=parsed_results.get("raw_metadata")
        )
        db.add(financial_data)
        await db.flush()

        for item in parsed_results.get("line_items", []):
            line_item = LineItem(financial_data_id=financial_data.id, **item)
            db.add(line_item)

        document.status = ProcessingStatus.COMPLETED
        logger.info(f"Successfully processed document ID: {document.id}")

    except Exception as e:
        logger.error(f"Execution failure parsing document ID: {document.id}. Details: {str(e)}")
        document.status = ProcessingStatus.FAILED
        document.error_message = str(e)
    
    await db.commit()
    
    # Reload with relational objects for structured response matching
    stmt = select(Document).where(Document.id == document.id).options(
        selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
    )
    result = await db.execute(stmt)
    return result.scalars().first()

# --- 2. QUERY & FILTER DOCUMENTS ---
@parser_router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    vendor: Optional[str] = Query(None),
    status: Optional[ProcessingStatus] = Query(None),
    doc_type: Optional[DocumentType] = Query(None),
    min_amount: Optional[float] = Query(None),
    max_amount: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Document).join(Document.parsed_data, isouter=True).options(
        selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
    )
    
    if status:
        stmt = stmt.where(Document.status == status)
    if doc_type:
        stmt = stmt.where(Document.document_type == doc_type)
    if vendor:
        stmt = stmt.where(ParsedFinancialData.vendor_name.ilike(f"%{vendor}%"))
    if min_amount is not None:
        stmt = stmt.where(ParsedFinancialData.amount >= min_amount)
    if max_amount is not None:
        stmt = stmt.where(ParsedFinancialData.amount <= max_amount)

    result = await db.execute(stmt)
    return result.scalars().all()

# --- 3. GET DOCUMENT BY ID ---
@parser_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == document_id).options(
        selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
    )
    result = await db.execute(stmt)
    document = result.scalars().first()
    if not document:
        raise HTTPException(status_code=404, detail="Requested target profile index element not found.")
    return document

# --- 4. UPDATE METADATA ---
@parser_router.put("/{document_id}/metadata", response_model=DocumentResponse)
async def update_metadata(document_id: int, payload: ParsedDataUpdate, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == document_id).options(
        selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
    )
    result = await db.execute(stmt)
    document = result.scalars().first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document entity missing.")
    if not document.parsed_data:
        raise HTTPException(status_code=400, detail="No valid operational data associated with document to mutate.")
    
    for key, value in payload.dict(exclude_unset=True).items():
        setattr(document.parsed_data, key, value)
        
    await db.commit()
    return document

# --- 5. DELETE DOCUMENT RECORD ---
@parser_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: int, db: AsyncSession = Depends(get_db)):
    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    document = result.scalars().first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Entity target could not be parsed for systemic purge.")
        
    await db.delete(document)
    await db.commit()
    return None