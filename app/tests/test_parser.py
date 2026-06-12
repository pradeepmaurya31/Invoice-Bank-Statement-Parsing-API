import asyncio
import pytest
from httpx import AsyncClient, ASGITransport 
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database.database import get_db, Base
from app.models.models import ProcessingStatus, DocumentType

# --- 1. Test Database Configuration Setup ---
# Setup an isolated, in-memory SQLite engine for parallelized test execution
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

@pytest.fixture(autouse=True)
async def setup_database():
    """Automatically builds and tears down schemas for every isolated test window."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# --- Add this loop scope management fixture ---
@pytest.fixture(scope="function")
def event_loop():
    """Provides an isolated event loop per test execution block."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# --- Explicitly register your autouse fixture with the pytest loop engine ---
@pytest.fixture(scope="function", autouse=True)
async def setup_database():
    """Automatically builds and tears down schemas for every isolated test window."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

# --- 2. Correct Dependency Override Pattern ---
@pytest.fixture(scope="function", autouse=True)
def override_database_dependency():
    """
    Safely injects the mock database session provider into FastAPI's 
    dependency overrides map without invoking the fixture directly.
    """
    async def _override_get_db():
        async with TestingSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # Register the internal generator override function
    app.dependency_overrides[get_db] = _override_get_db
    yield
    # Clean up after the test completes so it doesn't leak into other suites
    app.dependency_overrides.clear()

@pytest.fixture
async def client():
    """Asynchronous HTTP Client for hitting endpoints using HTTPX 0.28+ standards."""
    # Wrap the FastAPI application inside an ASGITransport instance
    transport = ASGITransport(app=app)
    
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

# --- 2. Test Suite Execution Cases ---

@pytest.mark.asyncio
async def test_upload_pdf_invoice_success(client: AsyncClient):
    """Verifies that a valid PDF invoice uploads and extracts structured data successfully."""
    # Simulate a file payload
    file_payload = {"file": ("invoice_2026.pdf", b"%PDF-1.4 mock content stream data", "application/pdf")}
    
    response = await client.post("/api/v1/documents/upload", files=file_payload)
    
    assert response.status_code == 201
    data = response.json()
    
    # Assert primary field mappings and UUID validity
    assert "id" in data
    assert UUID(data["id"])  # Confirms it is a valid UUID
    assert data["filename"] == "invoice_2026.pdf"
    assert data["document_type"] == DocumentType.PDF
    assert data["status"] == ProcessingStatus.COMPLETED
    
    # Assert extracted core metrics and nested line items
    assert data["parsed_data"]["vendor_name"] == "Acme Corp Ltd."
    assert data["parsed_data"]["amount"] == 1250.75
    assert len(data["parsed_data"]["line_items"]) == 2


@pytest.mark.asyncio
async def test_upload_csv_statement_success(client: AsyncClient):
    """Verifies that a valid CSV bank statement processes cleanly."""
    file_payload = {"file": ("statement.csv", b"TransactionDate,Description,Amount\n2026-06-01,Test,100", "text/csv")}
    
    response = await client.post("/api/v1/documents/upload", files=file_payload)
    
    assert response.status_code == 201
    data = response.json()
    assert data["document_type"] == DocumentType.CSV
    assert data["parsed_data"]["vendor_name"] == "Global Bank Corp"


@pytest.mark.asyncio
async def test_upload_invalid_file_extension(client: AsyncClient):
    """Verifies that unsupported file extensions are blocked at the gateway level."""
    file_payload = {"file": ("malicious_script.exe", b"executable bytes...", "application/octet-stream")}
    
    response = await client.post("/api/v1/documents/upload", files=file_payload)
    
    assert response.status_code == 400
    # Updated to match the new exception handler message
    assert "Unsupported format interface extension" in response.json()["detail"]


@pytest.mark.asyncio
async def test_upload_duplicate_file_prevention(client: AsyncClient):
    """Ensures our SHA256 deduplication logic prevents identical file uploads."""
    file_payload = {"file": ("duplicate_check.pdf", b"Unique file bytes payload structure", "application/pdf")}
    
    # First Upload: Expected to succeed
    resp1 = await client.post("/api/v1/documents/upload", files=file_payload)
    assert resp1.status_code == 201
    
    # Second Upload (Identical Bytes): Expected to trigger a conflict error
    resp2 = await client.post("/api/v1/documents/upload", files=file_payload)
    assert resp2.status_code == 409
    # Updated to match the new exception handler message
    assert "Duplicate asset trace" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_upload_file_size_limit_violation(client: AsyncClient):
    """Ensures oversized documents are rejected safely to prevent memory exhaustion."""
    # Generate mock byte stream larger than 10MB limit (e.g., 11MB)
    oversized_content = b"0" * (11 * 1024 * 1024)
    file_payload = {"file": ("huge_invoice.pdf", oversized_content, "application/pdf")}
    
    response = await client.post("/api/v1/documents/upload", files=file_payload)
    
    assert response.status_code == 400
    # Updated to match the new exception handler message
    assert "File capacity exceeds safety boundaries" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_document_by_id_not_found(client: AsyncClient):
    """Verifies that querying a non-existent UUID returns a clean 404 response."""
    random_uuid = str(uuid4())
    response = await client.get(f"/api/v1/documents/{random_uuid}")
    
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_update_metadata_successfully(client: AsyncClient):
    """Tests the correction capability for extracted financial properties."""
    # 1. Ingest a document first
    file_payload = {"file": ("invoice_to_edit.pdf", b"Some random invoice stream structure", "application/pdf")}
    setup_resp = await client.post("/api/v1/documents/upload", files=file_payload)
    doc_id = setup_resp.json()["id"]

    # 2. Issue a mutation payload to correct fields
    mutation_payload = {
        "vendor_name": "Acme Corp Extended Version",
        "amount": 9999.99,
        "currency": "EUR"
    }
    
    response = await client.put(f"/api/v1/documents/{doc_id}/metadata", json=mutation_payload)
    
    assert response.status_code == 200
    updated_data = response.json()["parsed_data"]
    assert updated_data["vendor_name"] == "Acme Corp Extended Version"
    assert updated_data["amount"] == 9999.99
    assert updated_data["currency"] == "EUR"


@pytest.mark.asyncio
async def test_delete_document_cascade(client: AsyncClient):
    """Verifies complete database cascading purge execution upon document deletion."""
    # 1. Ingest document
    file_payload = {"file": ("invoice_to_purge.pdf", b"Purge processing verification bytes", "application/pdf")}
    setup_resp = await client.post("/api/v1/documents/upload", files=file_payload)
    doc_id = setup_resp.json()["id"]
    
    # 2. Verify target exists
    check_resp = await client.get(f"/api/v1/documents/{doc_id}")
    assert check_resp.status_code == 200

    # 3. Purge target item
    delete_resp = await client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 204
    
    # 4. Confirm item is gone
    final_check = await client.get(f"/api/v1/documents/{doc_id}")
    assert final_check.status_code == 404