"""
FastAPI Worker Server
Receives scan requests from Edge Functions and returns VFS scan results
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
from vfs_scanner import VFSScanner
from country_configs import list_supported_countries, get_country_config

app = FastAPI(title="VFS Scanner Worker")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Authentication
WORKER_SECRET = os.getenv("WORKER_SECRET", "your-secret-key-change-this")

# Scanner instance (reuse browser)
scanner: Optional[VFSScanner] = None


@app.on_event("startup")
async def startup_event():
    """Initialize browser on startup"""
    global scanner
    print("🚀 Initializing VFS Scanner...")
    scanner = VFSScanner(headless=True)
    await scanner.init_browser()
    print("✅ Scanner ready!")


@app.on_event("shutdown")
async def shutdown_event():
    """Close browser on shutdown"""
    global scanner
    if scanner:
        print("🔒 Closing scanner...")
        await scanner.close_browser()


class ScanRequest(BaseModel):
    country_code: str
    country_name: str


class ScanResponse(BaseModel):
    success: bool
    country: str
    has_appointment: bool
    available_slots: Optional[List[str]]
    message: str
    scan_duration_ms: int


@app.get("/")
async def root():
    """Health check"""
    return {
        "service": "VFS Scanner Worker",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health")
async def health():
    """Health check for deployment platforms"""
    return {"status": "healthy"}


@app.post("/scan", response_model=ScanResponse)
async def scan_country(request: ScanRequest,
                       authorization: Optional[str] = Header(None)):
    """Scan VFS Global for appointments"""
    # Verify authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401,
                            detail="Missing or invalid authorization")

    token = authorization.replace("Bearer ", "")
    if token != WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret key")

    # Scan country
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")

    print(f"📋 Scanning: {request.country_name} ({request.country_code})")
    result = await scanner.scan_country(request.country_code,
                                        request.country_name)
    print(f"✅ Scan complete: {result['message']}")

    return result


@app.post("/scan-batch")
async def scan_batch(countries: List[ScanRequest],
                     authorization: Optional[str] = Header(None)):
    """Scan multiple countries in sequence"""
    # Verify authentication
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401,
                            detail="Missing or invalid authorization")

    token = authorization.replace("Bearer ", "")
    if token != WORKER_SECRET:
        raise HTTPException(status_code=403, detail="Invalid secret key")

    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")

    results = []
    found_count = 0

    for country in countries:
        print(f"📋 Scanning: {country.country_name} ({country.country_code})")
        result = await scanner.scan_country(country.country_code,
                                            country.country_name)
        results.append(result)

        if result['has_appointment']:
            found_count += 1

    return {
        "success": True,
        "scanned": len(results),
        "found": found_count,
        "results": results
    }


@app.get("/countries")
async def get_supported_countries():
    """Get list of supported countries"""
    return list_supported_countries()


@app.get("/countries/{country_code}")
async def get_country_config_endpoint(country_code: str):
    """Get configuration for a specific country"""
    config = get_country_config(country_code)

    return {
        "code":
        country_code,
        "name":
        config['name'],
        "url":
        config['appointment_url'],
        "supported":
        country_code.lower() in ['deu', 'bel', 'esp', 'fra', 'ita', 'nld']
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
