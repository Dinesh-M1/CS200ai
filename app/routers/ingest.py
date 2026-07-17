import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.versioning import ingest_document  # Core versioning logic

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/ingest", tags=["Ingest"])
def ingest_pdf_version(document_name: str, pdf_path: str, db: Session = Depends(get_db)):
    """
    Reads the PDF path, extracts its text using PyMuPDF, and runs your custom
    hierarchical Markdown parsing and version tracking algorithms.
    """
    try:
        # 1. Open and extract all text from the target PDF
        try:
            doc = fitz.open(pdf_path)
            extracted_text = ""
            for page in doc:
                extracted_text += page.get_text() + "\n"
        except Exception as pdf_err:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to read PDF from path '{pdf_path}': {str(pdf_err)}"
            )

        # 2. Feed the extracted text directly into your core document ingestion engine
        version_record = ingest_document(db, document_name, extracted_text)
        
        return {
            "status": "success",
            "message": f"Successfully processed '{document_name}' into Version {version_record.version_number}.",
            "version_number": version_record.version_number,
            "document_id": version_record.document_id
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")