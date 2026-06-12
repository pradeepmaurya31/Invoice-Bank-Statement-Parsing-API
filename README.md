# Invoice-Bank-Statement-Parsing-API
Organizations often receive financial documents from multiple vendors and banks in inconsistent formats. Manual processing is time-consuming and error-prone. This system acts as an internal tool to standardize and digitize financial data extraction for downstream analysis and reporting.

Here is a complete, production-ready `README.md` file tailored specifically to the project architecture shown in your image. It covers setup instructions, architecture breakdown, API endpoints, and a deployment plan to satisfy the hiring use case requirements.

---

```markdown
# Invoice & Bank Statement Parsing API

[cite_start]A production-grade, asynchronous FastAPI backend service designed to ingest PDF invoices and CSV bank statements, extract structured financial records, deduplicate uploads, and expose a robust, filterable REST API[cite: 3, 4, 21].

---



## 🏗️ Project Architecture

The repository follows a clean, modular layout separating concerns into domain-specific directories:

```text
├── .venv/                      # Python virtual environment
├── app/                        # Main application package
│   ├── configs/                # Configuration management
│   │   ├── __init__.py
│   │   └── config.py           # Environment variables & Settings (Pydantic)
│   ├── database/
│   │   └── database.py         # SQLAlchemy engine & async session setup
│   ├── manager/
│   │   └── parser.py           # Parsing strategies (Strategy Pattern for PDF/CSV)
│   ├── models/
│   │   └── models.py           # SQLAlchemy relational database models
│   ├── routes/
│   │   └── parser_routes.py    # FastAPI router endpoints
│   ├── schemas/
│   │   └── schemas.py          # Pydantic data validation schemas
│   ├── utils/
│   │   └── logger.py           # Structured application logging
│   ├── __init__.py
│   └── main.py                 # FastAPI app initialization & Lifespan setup
├── test_files/                 # Sample documents & testing utilities
│   ├── generate_pdf.py         # Utility script to mock an invoice PDF
│   ├── invoice_sample.pdf      # Sample PDF invoice
│   └── sample.csv              # Sample CSV bank statement
├── .env                        # Local active environment variables
├── .gitignore
├── docker-compose.yml          # Local multi-container orchestration
├── Dockerfile                  # Production container definition
├── example.env                 # Template for environment variables
├── README.md                   # Project documentation
└── requirements.txt            # Application dependencies

```

---

## 🚀 Quick Start & Setup

### Option 1: Running via Docker Compose (Recommended)

This spins up both the FastAPI backend and a health-checked PostgreSQL instance automatically.

1. Clone the repository and navigate to the root directory.
2. Create your `.env` file from the example template:
```bash
cp example.env .env

```


3. Boot up the environment:
```bash
docker-compose up --build

```


4. The API will be active at: `http://localhost:8000`
5. Interactive API docs (Swagger UI): `http://localhost:8000/docs` 



### Option 2: Local Virtual Environment

1. Create and activate a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate

```


2. Install the dependencies:
```bash
pip install -r requirements.txt

```


3. Set your `DATABASE_URL` and app settings in the local `.env` file.
4. Launch the server using Uvicorn:
```bash
uvicorn app.main:app --reload

```

## test case run command
```bash
pytest -v -s app/tests/test_parser.py

```

---

## 💾 Database Schema Explanation

The PostgreSQL database uses a fully normalized, relational structure designed to handle complex data relationships and preserve audit trails:

* 
**`documents` Table**: Tracks the top-level lifecycle of uploaded files. Stores metadata like `filename`, `document_type` (`PDF` or `CSV`), processing `status` (`PENDING`, `COMPLETED`, `FAILED`), and an `error_message` string if parsing breaks down. It features a unique `file_hash` column to enforce strict deduplication at the structural byte level.


* **`parsed_financial_data` Table**: Linked 1:1 with the `documents` table. It flattens standard financial indices for downstream analysis including `vendor_name`, total `amount`, currency code, and `invoice_date`. It also houses a flexible `raw_metadata` `JSON` column to capture unmapped or non-standard vendor attributes seamlessly.


* **`line_items` Table**: Linked 1:N (one-to-many) with `parsed_financial_data`. Captures granular transaction breakdowns, tracking descriptive fields, item volume units (`quantity`), individual item valuations (`unit_price`), and cumulative row balances (`total_price`).



---

## ⚡ API Endpoints Summary

All core application actions are exposed through clean RESTful asynchronous endpoints:

| Method | Endpoint | Description |
| --- | --- | --- |
| **POST** | `/api/v1/documents/upload` | Stream-uploads file (`.pdf`/`.csv`), validates dimensions, checks hashes for duplicates, and parses transactional metadata.

 |
| **GET** | `/api/v1/documents` | Queries collected documents. Supports filtering by vendor string, min/max monetary caps, status fields, and doc types.

 |
| **GET** | `/api/v1/documents/{id}` | Fetches detailed operational entity records alongside nested parsed line items.

 |
| **PUT** | `/api/v1/documents/{id}/metadata` | Mutates or corrects parsed data points manually (e.g., editing a misread vendor name).

 |
| **DELETE** | `/api/v1/documents/{id}` | Purges the target document and its cascading relational database items cleanly.

 |

---

## ☁️ Cloud Deployment Plan

To transition this service to a scalable production cloud environment, the following architecture is recommended:

1. 
**Compute Layer**: Deploy the containerized FastAPI application to **AWS ECS (Fargate)** or **GCP Cloud Run** to achieve automated scaling, high availability, and serverless resource provisioning.


2. 
**Database Layer**: Replace the containerized PostgreSQL database with a managed instance such as **AWS RDS (PostgreSQL)** or **GCP Cloud SQL**, configuring automated snapshots, point-in-time recovery, and multi-AZ replication.


3. **Storage Tier**: In a multi-worker production cluster, local file reading is fragile. Uploaded files should stream directly to a durable object storage bucket like **AWS S3** or **Google Cloud Storage**. The database should store the object reference URI instead of local paths.


4. 
**Asynchronous Scaling (Future Scope)**: For processing large volumes of documents, decouple the parsing execution entirely. The API layer should write incoming file jobs to a message broker (**Celery + Redis / AWS SQS**), allowing dedicated background workers to digest and parse documents asynchronously without blocking client HTTP threads.



---

## ⚠️ Assumptions & Known Limitations

* 
**Deterministic Mock Parsers**: The internal strategies currently implement mock heuristic logic designed to demonstrate clean architectural routing, validation, and structural entry. Production upgrades require dropping real extraction libraries (e.g., `pdfplumber`, `pypdf`, or optical AI engines) directly into `app/manager/parser.py`.


* 
**In-Memory File Reads**: Files are buffered into system memory during ingestion for hashing validation. For extremely large processing workloads (files exceeding 50MB+), this should be refactored to read streaming chunks via temporary disk spools to maintain safe memory consumption.



```

```