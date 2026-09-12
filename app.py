from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from auth import router as auth_router
from contacts import router as contact_router
from accident import router as accident_router

app = FastAPI(
    title="LifeGuard AI Backend",
    version="1.0.0",
    description="Emergency Crash Detection, Auto SOS Cascade & Hospital/Police Command System"
)

# ================= CORS CONFIGURATION =================
# Web Dashboard, Flutter App matrum External APIs smooth-aaga access seiya
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ================= STATIC FOLDER (OPTIONAL UI ASSETS) =================
if not os.path.exists("static"):
    os.makedirs("static")

app.mount("/static", StaticFiles(directory="static"), name="static")

# ================= ROUTERS =================
# 1. Login & Registration
app.include_router(auth_router)

# 2. Emergency Contacts
app.include_router(contact_router)

# 3. SOS Dispatch, Hospital & Police Portals, Auto-Cascade Engine
app.include_router(accident_router)

# ================= ROOT ENDPOINT =================
@app.get("/")
def home():
    return {
        "status": "success",
        "service": "LifeGuard AI Cloud Engine",
        "message": "LifeGuard AI Backend & Cascade Dispatch Running Successfully",
        "database": "Cloud Firestore Active"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)