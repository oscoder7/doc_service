import os
import io
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, status,Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from docxtpl import DocxTemplate
from utils.api_fetcher import GenericApiFetcher


from fastapi import FastAPI, Header
from pydantic import BaseModel
from typing import List, Any, Optional


from datetime import datetime



app = FastAPI(
    title="Document Generation & Data Lookup Microservice",
    version="1.0.0",
    description="FastAPI service for Ref Cursor JSON conversions and docxtpl rendering"
)

# Base directory where Flask uploads docx templates
# Point this to Flask's upload folder if running on the same machine
TEMPLATE_DIR = os.environ.get('TEMPLATE_DIR') or os.path.abspath("../flask_contract_app/uploaded_templates")
# Ensure directory exists on startup so you don't get FileNotFoundError
os.makedirs(TEMPLATE_DIR, exist_ok=True)
# Request Models



class LookupRequest(BaseModel):
    application_ref: str
    process_code: str

class RenderRequest(BaseModel):
    template_name: str
    version_number: str
    application_ref: Optional[str] = "NO_REF"
    context: Dict[str, Any]
class SampleEndpointRequest(BaseModel):
    application_reference: Optional[str] = "DEFAULT_REF"
    process_code: Optional[str] = "SampleContract"
@app.post("/api/sample-endpoint")
async def sample_endpoint(request: Request, body: SampleEndpointRequest):
    """
    Simulates a core banking API endpoint. 
    It checks incoming headers (like Authorization bearer tokens) and returns 
    a mock payload populated with the requested application reference.
    """
    # 1. Optional: Inspect headers to verify Authorization is being passed correctly
    auth_header = request.headers.get("Authorization")
    if auth_header:
        print(f"Received Authorization Header: {auth_header}")
        # You can add token validation logic here if desired

    app_ref = body.application_reference

    # 2. Return a rich mock payload suitable for contract generation templates
    return {
        "application_ref": app_ref,
        "process_code": body.process_code,
        "contract_date": "2026-10-10",
        "applicant": {
            "name": "Anwar Al-Hinai",
            "civil_id": "109823912",
            "nationality": "Omani",
            "phone": "+968 91234567",
            "email": "anwar@example.com"
        },
        "contract_details": {
            "amount": 55000.00,
            "currency": "OMR",
            "term_months": 120,
            "monthly_installment": 520.00,
            "interest_rate": "4.25%"
        },
        "property_info": {
            "property_type": "Commercial Office",
            "location": "Al Khuwair, Muscat, Oman",
            "plot_number": "P-44210"
        },
        "status": "APPROVED"
    }


class ParamSC(BaseModel):
    paramName: str
    paramValue: Any

class ProcedureRequest(BaseModel):
    prcNo: int
    paramsSCs: List[ParamSC]

@app.post("/api/v1/execute-procedure")
async def execute_procedure(
    payload: ProcedureRequest,
    authorization: Optional[str] = Header(None)
):
    # Extract dynamic parameters from paramsSCs array
    params_dict = {p.paramName: p.paramValue for p in payload.paramsSCs}
    app_ref = params_dict.get("app_ref", "UNKNOWN_REF")

    print(f"Executing Procedure #{payload.prcNo} for Application Ref: {app_ref}")

    # Returning your original fields nested inside the core banking hashList format
    return {
        "errorCode": 0,
        "errorDesc": None,
        "hashList": [
            {
                "application_ref": app_ref,
                "contract_date": "2026-10-10",
                "applicant_name": "Anwar Al-Hinai",
                "civil_id": "109823912",
                "nationality": "Omani",
                "phone": "+968 91234567",
                "email": "anwar@example.com",
                "amount": 55000.0,
                "currency": "OMR",
                "term_months": 120,
                "monthly_installment": 520.0,
                "interest_rate": "4.25%",
                "property_type": "Commercial Office",
                "location": "Al Khuwair, Muscat, Oman",
                "plot_number": "P-44210",
                "status": "APPROVED"
            }
        ]
    }    
# --- 1. DATA LOOKUP ENDPOINT ---
fetcher = GenericApiFetcher() # Loads your template_api_map.json automatically
@app.post("/api/data-lookup")
def data_lookup(req: LookupRequest):
    try:
        # Uses your GenericApiFetcher class to query the configured external/sample endpoint
        data = fetcher.execute_process(process_code=req.process_code, app_ref=req.application_ref)
        return data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



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
