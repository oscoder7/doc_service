import os
import io
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from docxtpl import DocxTemplate

from datetime import datetime

app = FastAPI(
    title="Document Generation & Data Lookup Microservice",
    version="1.0.0",
    description="FastAPI service for Ref Cursor JSON conversions and docxtpl rendering"
)

# Base directory where Flask uploads docx templates
# Point this to Flask's upload folder if running on the same machine
TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR') or os.path.abspath("../flask_contract_app/uploaded_templates")

# Request Models
class LookupRequest(BaseModel):
    application_ref: str
    process_code: str

class RenderRequest(BaseModel):
    template_name: str
    version_number: str
    application_ref: Optional[str] = "NO_REF"
    context: Dict[str, Any]


# --- 1. DATA LOOKUP ENDPOINT ---
@app.post("/api/data-lookup")
async def data_lookup(req: LookupRequest):
    """
    Simulates / Executes the database procedure / Ref Cursor wrapper.
    In production, call your DB wrapper here using req.process_code.
    """
    if not req.application_ref or not req.process_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Application reference and process code are required"
        )

    # Example Mock payload returned from DB procedure wrapper
    mock_payload = {
        "application_ref": req.application_ref,
        "process_code": req.process_code,
        "contract_date": "2026-10-09",
        "applicant": {
            "name": "Anwar H.",
            "civil_id": "109823912",
            "nationality": "Omani",
            "phone": "+968 91234567",
            "email": "anwar@example.com"
        },
        "contract_details": {
            "amount": 45000.00,
            "currency": "OMR",
            "term_months": 60,
            "monthly_installment": 750.00,
            "interest_rate": "4.5%"
        },
        "property_info": {
            "property_type": "Residential Villa",
            "location": "Muscat, Oman",
            "plot_number": "P-99201"
        },
        "status": "APPROVED"
    }

    return mock_payload


# --- 2. DOCX TEMPLATE RENDERING ENDPOINT ---
@app.post("/api/generate-docx")
async def generate_docx(req: RenderRequest):
    """
    Receives JSON context and template specifications.
    Renders Jinja2 tags into the .docx file in RAM and streams bytes back.
    """
    # 1. Locate the file on disk
    possible_files = [
        f"{req.template_name}_{req.version_number}.docx",
        f"{req.template_name}_{req.version_number}_*.docx"
    ]

    target_file = None
    if os.path.exists(TEMPLATE_DIR):
        for f in os.listdir(TEMPLATE_DIR):
            if f.startswith(f"{req.template_name}_{req.version_number}") and f.endswith(".docx"):
                target_file = os.path.join(TEMPLATE_DIR, f)
                break

    # Check local fallback directory if not found in Flask upload folder
    if not target_file:
        local_dir = os.path.abspath("doc_templates")
        if os.path.exists(local_dir):
            for f in os.listdir(local_dir):
                if f.startswith(f"{req.template_name}_{req.version_number}") and f.endswith(".docx"):
                    target_file = os.path.join(local_dir, f)
                    break

    if not target_file or not os.path.exists(target_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template file for '{req.template_name}' (v{req.version_number}) not found on disk"
        )

    try:
        # 2. Render template in RAM using docxtpl
        doc = DocxTemplate(target_file)
        doc.render(req.context)

        # 3. Save rendered document to in-memory bytes buffer
        file_stream = io.BytesIO()
        doc.save(file_stream)
        file_stream.seek(0)

        # Build formatted filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        clean_name = req.template_name.replace(" ", "_")
        clean_ref = req.application_ref.replace(" ", "_")
        
        download_filename = f"{clean_name}_v{req.version_number}_{clean_ref}_{timestamp}.docx"

        # 4. Stream binary back to Flask
        return StreamingResponse(
            file_stream,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{download_filename}"'}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render Word document: {str(e)}"
        )

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "fastapi-doc-engine"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
