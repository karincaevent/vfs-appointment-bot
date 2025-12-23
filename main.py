"""
FastAPI Worker Server for VFS Appointment Bot
Receives scan requests from Edge Functions and returns VFS scan results
Version: 1.2.0 - Force deploy with VFS credentials support
"""
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import asyncio
from vfs_scanner import VFSScanner
from country_configs import list_supported_countries, get_country_config
from human_behavior import HumanBehavior

app = FastAPI(title="VFS Scanner Worker")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your Edge Function URL
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
    vfs_credentials: Optional[Dict] = None  # 🔥 NEW: VFS login credentials
    email_credentials: Optional[Dict] = None  # Email credentials for OTP
    vfs_session: Optional[Dict] = None  # 🔥 NEW: Manual session data (JWT, csk_str)
    proxy_config: Optional[Dict] = None  # 🔥 NEW: BrightData proxy config (username, password)


class ScanResponse(BaseModel):
    success: bool
    country: str
    has_appointment: bool
    available_slots: Optional[List[str]]
    message: str
    scan_duration_ms: int
    session_saved: Optional[bool] = False  # Indicates if new session was saved


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
async def scan_country(
    request: ScanRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Scan VFS Global for appointments
    
    Headers:
        Authorization: Bearer <WORKER_SECRET>
    
    Body:
        {
            "country_code": "deu",
            "country_name": "Germany",
            "vfs_credentials": {  # Optional - if provided, will login first
                "vfs_email": "user@example.com",
                "vfs_password": "password123",
                "application_center": "Istanbul"
            }
        }
    
    Returns:
        {
            "success": true,
            "country": "Germany",
            "has_appointment": true,
            "available_slots": ["2024-01-15", "2024-01-16"],
            "message": "Found 2 available slots",
            "scan_duration_ms": 3450
        }
    """
    # TEMPORARY: Skip authentication for testing
    # TODO: Re-enable in production
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    # 
    # token = authorization.replace("Bearer ", "")
    # if token != WORKER_SECRET:
    #     raise HTTPException(status_code=403, detail="Invalid secret key")
    
    # Scan country
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    print(f"📋 Scanning: {request.country_name} ({request.country_code})")
    print(f"📦 Full request received:", {
        "country_code": request.country_code,
        "country_name": request.country_name,
        "has_vfs_credentials": request.vfs_credentials is not None,
        "vfs_credentials_keys": list(request.vfs_credentials.keys()) if request.vfs_credentials else []
    })
    
    # 🔥 NEW: Log credentials status
    if request.vfs_credentials:
        print(f"🔐 VFS credentials provided: {request.vfs_credentials.get('vfs_email', 'N/A')}")
        print(f"   Application Center: {request.vfs_credentials.get('application_center', 'N/A')}")
        print(f"   Has encrypted password: {'vfs_password_encrypted' in request.vfs_credentials}")
        print(f"   Has plain password: {'vfs_password' in request.vfs_credentials}")
    else:
        print(f"⚠️  No VFS credentials - using direct URL")
    
    # Decrypt passwords if needed (in production, use proper decryption)
    if request.vfs_credentials and 'vfs_password_encrypted' in request.vfs_credentials:
        try:
            import base64
            request.vfs_credentials['vfs_password'] = base64.b64decode(
                request.vfs_credentials['vfs_password_encrypted']
            ).decode()
            print(f"🔓 Password decrypted successfully")
        except Exception as e:
            print(f"⚠️  Password decryption failed: {e}")
    
    # 🔥 NEW: Perform scan with credentials
    result = await scanner.scan_country(
        country_code=request.country_code,
        country_name=request.country_name,
        user_id="demo-user",  # 🔥 FIXED USER ID
        vfs_credentials=request.vfs_credentials,  # 🔥 PASS CREDENTIALS!
        email_credentials=request.email_credentials,  # 🔥 PASS EMAIL CREDENTIALS!
        vfs_session=request.vfs_session,  # 🔥 NEW: PASS MANUAL SESSION!
        proxy_config=request.proxy_config  # 🔥 NEW: PASS PROXY CONFIG!
    )
    
    print(f"✅ Scan complete: {result['message']}")
    
    return result


@app.post("/scan-batch")
async def scan_batch(
    countries: List[ScanRequest],
    authorization: Optional[str] = Header(None)
):
    """
    Scan multiple countries in sequence
    
    Headers:
        Authorization: Bearer <WORKER_SECRET>
    
    Body:
        [
            {"country_code": "deu", "country_name": "Germany"},
            {"country_code": "bel", "country_name": "Belgium"}
        ]
    
    Returns:
        {
            "success": true,
            "scanned": 2,
            "found": 1,
            "results": [...]
        }
    """
    # TEMPORARY: Skip authentication for testing
    # TODO: Re-enable in production
    # if not authorization or not authorization.startswith("Bearer "):
    #     raise HTTPException(status_code=401, detail="Missing or invalid authorization")
    # 
    # token = authorization.replace("Bearer ", "")
    # if token != WORKER_SECRET:
    #     raise HTTPException(status_code=403, detail="Invalid secret key")
    
    if not scanner:
        raise HTTPException(status_code=503, detail="Scanner not initialized")
    
    results = []
    found_count = 0
    
    for i, country in enumerate(countries):
        print(f"📋 Scanning {i+1}/{len(countries)}: {country.country_name} ({country.country_code})")
        
        # 🔥 NEW: Pass credentials to scanner
        result = await scanner.scan_country(
            country_code=country.country_code,
            country_name=country.country_name,
            user_id="demo-user",  # 🔥 FIXED USER ID
            vfs_credentials=country.vfs_credentials,  # 🔥 PASS CREDENTIALS!
            email_credentials=country.email_credentials,  # 🔥 PASS EMAIL CREDENTIALS!
            vfs_session=country.vfs_session,  # 🔥 NEW: PASS MANUAL SESSION!
            proxy_config=country.proxy_config  # 🔥 NEW: PASS PROXY CONFIG!
        )
        results.append(result)
        
        if result['has_appointment']:
            found_count += 1
        
        # 🚨 CRITICAL: Add delay between countries (human behavior)
        if i < len(countries) - 1:  # Don't wait after last country
            delay_ms = HumanBehavior.get_random_country_scan_delay()
            delay_sec = delay_ms / 1000
            print(f"⏳ Waiting {delay_sec/60:.1f} minutes before next country...")
            await asyncio.sleep(delay_sec)
    
    return {
        "success": True,
        "scanned": len(results),
        "found": found_count,
        "results": results
    }


@app.get("/countries")
async def get_supported_countries():
    """
    Get list of supported countries
    
    Returns:
        [
            {"code": "deu", "name": "Germany"},
            {"code": "bel", "name": "Belgium"},
            ...
        ]
    """
    return list_supported_countries()


@app.get("/countries/{country_code}")
async def get_country_config_endpoint(country_code: str):
    """
    Get configuration for a specific country
    
    Returns country config including URL and selectors
    """
    config = get_country_config(country_code)
    
    # Don't expose internal selectors (security)
    return {
        "code": country_code,
        "name": config['name'],
        "url": config['appointment_url'],
        "supported": country_code.lower() in ['deu', 'bel', 'esp', 'fra', 'ita', 'nld']
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
