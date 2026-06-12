from uuid import UUID
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
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
    # 1. Structural Format and Suffix Gate Check
    if not file.filename or "." not in file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Malformed file structure header: Missing file extension format type."
        )

    extension = file.filename.split(".")[-1].lower()
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Unsupported format interface extension. Allowed profiles: {settings.ALLOWED_EXTENSIONS}"
        )
    
    # 2. File Payload Stream Reading Guard
    try:
        content = await file.read()
    except Exception as read_err:
        logger.error(f"Inbound stream parsing read breakdown: {str(read_err)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Unreadable content stream binary data payload."
        )

    # 3. Size Constraint Guard
    if len(content) > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"File capacity exceeds safety boundaries limit constraint of {settings.MAX_FILE_SIZE_MB}MB."
        )
    
    # 4. Identity Signature Deduplication Check
    file_hash = generate_file_hash(content)
    try:
        existing_doc_query = await db.execute(select(Document).where(Document.file_hash == file_hash))
        if existing_doc_query.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, 
                detail="Duplicate asset trace: This exact file data footprint already exists in the system."
            )
    except HTTPException:
        raise
    except SQLAlchemyError as hash_db_err:
        logger.error(f"Database lookup exception encountered during data deduplication: {str(hash_db_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="System storage lookup error occurred while running parsing initialization parameters."
        )

    # 5. Pipeline Genesis Log Creation (Set state to PENDING)
    doc_type = DocumentType.PDF if extension == "pdf" else DocumentType.CSV
    document = Document(filename=file.filename, file_hash=file_hash, document_type=doc_type, status=ProcessingStatus.PENDING)
    
    try:
        db.add(document)
        await db.flush()  # Extract the operational runtime ID safely
    except SQLAlchemyError as pipeline_init_err:
        await db.rollback()
        logger.error(f"Failed to generate core pipeline logging tracker row: {str(pipeline_init_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Could not open a secure data tracking session sequence framework."
        )

    # 6. Strategic Document Parser Logic Block
    try:
        parser = DocumentParserFactory.get_parser(file.filename)
        parsed_results = parser.parse(content)
        
        # Hydrate financial details
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

        # Build subline data mapping links
        for item in parsed_results.get("line_items", []):
            line_item = LineItem(financial_data_id=financial_data.id, **item)
            db.add(line_item)

        document.status = ProcessingStatus.COMPLETED
        logger.info(f"Successfully finalized parsing processing for target workflow session: {document.id}")

    except (ValueError, TypeError, KeyError) as validation_mapping_error:
        # Gracefully handle structural anomalies or dirty layout parameters inside specific files
        await db.rollback()
        document.status = ProcessingStatus.FAILED
        document.error_message = f"Data Format Mapping Exception: {str(validation_mapping_error)}"
        logger.warning(f"Handled inconsistent text layout structure on asset tracking node {document.id}: {str(validation_mapping_error)}")
        
        # Save processing failure metadata state back to the tracking table for audit logging
        db.add(document)
        await db.commit()
    except Exception as unpredictable_engine_failure:
        # Global safety catch for underlying driver or library issues
        await db.rollback()
        document.status = ProcessingStatus.FAILED
        document.error_message = f"Core Extraction Engine Anomaly: {str(unpredictable_engine_failure)}"
        logger.error(f"Unpredicted systemic failure processing document session tracking index {document.id}: {str(unpredictable_engine_failure)}")
        
        db.add(document)
        await db.commit()
    else:
        await db.commit()
    
    # 7. Materialize Output View Generation
    try:
        stmt = select(Document).where(Document.id == document.id).options(
            selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
        )
        result = await db.execute(stmt)
        return result.scalars().first()
    except SQLAlchemyError as compilation_view_err:
        logger.error(f"Relational output payload compilation layer view tracking crashed: {str(compilation_view_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Transaction persisted cleanly, but response serialization view mapping generated an issue."
        )


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
    try:
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
    except SQLAlchemyError as query_list_err:
        logger.error(f"Database query filter transaction generated an error: {str(query_list_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Database filter processing service pipeline layer is down or unreachable."
        )


# --- 3. GET DOCUMENT BY ID ---
@parser_router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).where(Document.id == document_id).options(
            selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
        )
        result = await db.execute(stmt)
        document = result.scalars().first()
    except SQLAlchemyError as retrieve_err:
        logger.error(f"Database extraction error encountered for index parameter token {document_id}: {str(retrieve_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Internal search storage querying execution failure."
        )
        
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="The targeted document record index reference element was not found."
        )
    return document


# --- 4. UPDATE METADATA (WITH TIMEZONE CONSTRAINTS PROTECTION) ---
@parser_router.put("/{document_id}/metadata", response_model=DocumentResponse)
async def update_metadata(document_id: UUID, payload: ParsedDataUpdate, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).where(Document.id == document_id).options(
            selectinload(Document.parsed_data).selectinload(ParsedFinancialData.line_items)
        )
        result = await db.execute(stmt)
        document = result.scalars().first()
    except SQLAlchemyError as lookup_err:
        logger.error(f"Pre-mutation lookups database query error context step failed: {str(lookup_err)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Storage service connection issue.")
    
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document asset item targeted could not be found.")
    if not document.parsed_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No extractable operational data attributes present to mutate.")
    
    try:
        for key, value in payload.dict(exclude_unset=True).items():
            # Strips Timezone offset values explicitly to prevent offset-naive/aware TIMESTAMP database validation failures
            if key == "invoice_date" and value is not None and getattr(value, "tzinfo", None) is not None:
                value = value.replace(tzinfo=None)
                
            setattr(document.parsed_data, key, value)
            
        await db.commit()  # Flush context parameters safely to database node
        
    except IntegrityError as integrity_constraint_err:
        await db.rollback()
        logger.warning(f"Metadata value adjustments rejected due to index parameter constraints: {str(integrity_constraint_err)}")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Data mutations break unique entity table tracking criteria.")
    except Exception as data_type_mismatch_err:
        await db.rollback()  # Clears broken/invalid transactions out of session state safely
        logger.error(f"Critical exception encountered executing metadata parameter changes updates: {str(data_type_mismatch_err)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database rejected fields mutation format configuration properties data types matching criteria.")
        
    return document


# --- 5. CASCADING DELETE DOCUMENT RECORD ---
@parser_router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: UUID, db: AsyncSession = Depends(get_db)):
    try:
        stmt = select(Document).where(Document.id == document_id)
        result = await db.execute(stmt)
        document = result.scalars().first()
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Target operational entity requested for purge tracking profile could not be located."
            )
            
        await db.delete(document)
        await db.commit()
    except HTTPException:
        raise
    except SQLAlchemyError as deletion_sweep_err:
        await db.rollback()
        logger.error(f"Cascading record purge action block failed downstream relationship deletions: {str(deletion_sweep_err)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Database entity link locks blocked deletion workflow processing context parameters."
        )
    return None