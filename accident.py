import asyncio
import math
import requests
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

router = APIRouter()

PROJECT_ID = "lifeguard-ai-1dff7"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"
SERVER_IP = "lifeguard-backend-lii5.onrender.com"
def firestore_get(collection: str, doc_id: str = ""):
    url = f"{FIRESTORE_BASE_URL}/{collection}" + (f"/{doc_id}" if doc_id else "")
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Firestore GET Error ({collection}): {e}")
    return None

def firestore_patch(collection: str, doc_id: str, fields: dict):
    url = f"{FIRESTORE_BASE_URL}/{collection}/{doc_id}"
    update_mask = "&".join([f"updateMask.fieldPaths={k}" for k in fields.keys()])
    full_url = f"{url}?{update_mask}"
    formatted_fields = {}
    for k, v in fields.items():
        if isinstance(v, str):
            formatted_fields[k] = {"stringValue": v}
        elif isinstance(v, (int, float)):
            formatted_fields[k] = {"doubleValue": float(v)}
        elif isinstance(v, bool):
            formatted_fields[k] = {"booleanValue": v}
    try:
        res = requests.patch(full_url, json={"fields": formatted_fields}, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"Firestore PATCH Error: {e}")
        return False

def firestore_post(collection: str, fields: dict):
    url = f"{FIRESTORE_BASE_URL}/{collection}"
    formatted_fields = {}
    for k, v in fields.items():
        if isinstance(v, str):
            formatted_fields[k] = {"stringValue": v}
        elif isinstance(v, (int, float)):
            formatted_fields[k] = {"doubleValue": float(v)}
        elif isinstance(v, bool):
            formatted_fields[k] = {"booleanValue": v}
    try:
        res = requests.post(url, json={"fields": formatted_fields}, timeout=5)
        if res.status_code == 200:
            doc_name = res.json().get("name", "")
            return doc_name.split("/")[-1]
    except Exception as e:
        print(f"Firestore POST Error: {e}")
    return None

def parse_doc(doc: dict):
    data = {}
    fields = doc.get("fields", {})
    for k, v in fields.items():
        if "stringValue" in v:
            data[k] = v["stringValue"]
        elif "doubleValue" in v:
            data[k] = float(v["doubleValue"])
        elif "integerValue" in v:
            data[k] = int(v["integerValue"])
        elif "booleanValue" in v:
            data[k] = v["booleanValue"]
    data["id"] = doc.get("name", "").split("/")[-1]
    return data

def send_real_sms(recipient_type, phone_numbers, message_text):
    if not message_text:
        return
    clean_numbers = []
    if phone_numbers:
        for p in phone_numbers:
            if p:
                num = str(p).replace("+91", "").replace(" ", "").replace("-", "").strip()
                if len(num) == 10 and num.isdigit():
                    clean_numbers.append(num)
    numbers_str = ", ".join(clean_numbers) if clean_numbers else "No Targets"
    print(f"\n=======================================================")
    print(f"📡 [EMERGENCY ALERT DISPATCH -> {recipient_type.upper()}]")
    print(f"📞 Contact Targets : {numbers_str}")
    print(f"💬 Alert Content   : {message_text}")
    print(f"=======================================================\n")

class SOSRequest(BaseModel):
    user_id: int
    latitude: float
    longitude: float

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = (math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(R * c, 2)
def get_ranked_hospitals(latitude, longitude, attempt=0):
    ranked = []
    try:
        radii = [15000, 40000, 80000]
        radius = radii[attempt] if attempt < len(radii) else radii[-1]
        
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:5];
        (
          node["amenity"="hospital"](around:{radius},{latitude},{longitude});
          way["amenity"="hospital"](around:{radius},{latitude},{longitude});
          node["amenity"="clinic"](around:{radius},{latitude},{longitude});
        );
        out body;
        """
        response = requests.post(overpass_url, data=query, timeout=6)
        if response.status_code == 200:
            elements = response.json().get("elements", [])
            for el in elements:
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                name = el.get("tags", {}).get("name", "Local Medical Center")
                if lat and lon:
                    dist = calculate_distance(latitude, longitude, lat, lon)
                    ranked.append({
                        "name": name,
                        "phone": "7708917685",
                        "latitude": lat,
                        "longitude": lon,
                        "distance_km": dist
                    })
    except Exception as e:
        print(f"Overpass API Hospital Error: {e}")

    # ஓவர்வாட்ச் ஏபிஐ-ல் டேட்டா கிடைக்கவில்லை என்றால் மட்டும் ஃபால்பக் பெயர்
    if not ranked:
        ranked.append({
            "name": f"General Hospital (Attempt {attempt+1})",
            "phone": "7708917685",
            "latitude": latitude + 0.01,
            "longitude": longitude + 0.01,
            "distance_km": 1.5
        })

    ranked.sort(key=lambda x: x["distance_km"])
    return ranked

def get_ranked_police_stations(latitude, longitude, attempt=0):
    ranked = []
    try:
        radii = [15000, 40000, 80000]
        radius = radii[attempt] if attempt < len(radii) else radii[-1]
        
        overpass_url = "http://overpass-api.de/api/interpreter"
        query = f"""
        [out:json][timeout:5];
        (
          node["amenity"="police"](around:{radius},{latitude},{longitude});
          way["amenity"="police"](around:{radius},{latitude},{longitude});
        );
        out body;
        """
        response = requests.post(overpass_url, data=query, timeout=6)
        if response.status_code == 200:
            elements = response.json().get("elements", [])
            for el in elements:
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                name = el.get("tags", {}).get("name", "Local Police Station")
                if lat and lon:
                    dist = calculate_distance(latitude, longitude, lat, lon)
                    ranked.append({
                        "name": name,
                        "phone": "9363928690",
                        "latitude": lat,
                        "longitude": lon,
                        "distance_km": dist
                    })
    except Exception as e:
        print(f"Overpass API Police Error: {e}")

    if not ranked:
        ranked.append({
            "name": f"City Police Control Room (Attempt {attempt+1})",
            "phone": "9363928690",
            "latitude": latitude + 0.012,
            "longitude": longitude + 0.012,
            "distance_km": 2.0
        })

    ranked.sort(key=lambda x: x["distance_km"])
    return ranked

async def process_hospital_auto_cascade(doc_id: str, user_name: str, maps_link: str, initial_lat: float, initial_lon: float):
    attempt = 0
    while True:
        ranked_hospitals = get_ranked_hospitals(initial_lat, initial_lon, attempt)
        if attempt >= len(ranked_hospitals):
            attempt = 0
        doc = firestore_get("emergency_requests", doc_id)
        if doc:
            data = parse_doc(doc)
            if data.get("status") == "ACCEPTED" or data.get("hospital_status") == "ACCEPTED":
                break
        current_hosp = ranked_hospitals[attempt]
        hosp_phone = current_hosp.get("phone")
        hospital_portal_link = f"http://{SERVER_IP}/hospital-portal/{doc_id}?attempt={attempt}"
        hosp_sms = f"🚨 RED ALERT: Crash near {current_hosp['name']} ({current_hosp['distance_km']} km). Victim: {user_name}. Open Live Tracking Portal: {hospital_portal_link}"
        if hosp_phone:
            send_real_sms(f"Hospital [Rank #{attempt+1}]", [hosp_phone], hosp_sms)
        is_accepted = False
        for _ in range(12):
            await asyncio.sleep(5)
            chk_doc = firestore_get("emergency_requests", doc_id)
            if chk_doc:
                chk = parse_doc(chk_doc)
                if chk.get("status") == "ACCEPTED" or chk.get("hospital_status") == "ACCEPTED":
                    is_accepted = True
                    break
        if is_accepted:
            break
        attempt += 1

@router.post("/sos")
def send_sos(data: SOSRequest, background_tasks: BackgroundTasks):
    try:
        user_doc = firestore_get("users", str(data.user_id))
        user_name = "LifeGuard User"
        if user_doc:
            user_name = parse_doc(user_doc).get("name", "LifeGuard User")
        contacts_res = firestore_get(f"users/{data.user_id}/contacts")
        phone_list = []
        if contacts_res and "documents" in contacts_res:
            for c in contacts_res["documents"]:
                p = parse_doc(c).get("phone")
                if p:
                    phone_list.append(str(p))
        ranked_hospitals = get_ranked_hospitals(data.latitude, data.longitude, 0)
        ranked_police = get_ranked_police_stations(data.latitude, data.longitude, 0)
        primary_hospital = ranked_hospitals[0] if ranked_hospitals else None
        primary_police = ranked_police[0] if ranked_police else None
        doc_id = firestore_post("emergency_requests", {
            "user_id": data.user_id,
            "latitude": data.latitude,
            "longitude": data.longitude,
            "status": "En Route",
            "hospital_status": "Dispatched",
            "police_status": "Alerted",
            "hospital_name": primary_hospital["name"] if primary_hospital else "Nearest Hospital",
            "police_name": primary_police["name"] if primary_police else "Nearest Police",
            "created_at": datetime.utcnow().isoformat(),
        })
        maps_link = f"https://maps.google.com/?q={data.latitude},{data.longitude}"
        police_portal_link = f"http://{SERVER_IP}/police-portal/{doc_id}?attempt=0"
        hospital_portal_link = f"http://{SERVER_IP}/hospital-portal/{doc_id}?attempt=0"

        # முதல் எமர்ஜென்சி அலர்ட் மெசேஜ் (Safe வார்த்தை நீக்கப்பட்டது)
        family_sms = f"🚨 EMERGENCY CRASH ALERT! {user_name} met with an accident. Urgent help needed! Open Live Portal: {hospital_portal_link} | Map: {maps_link}"
        send_real_sms("Family", phone_list, family_sms)

        if primary_police and primary_police.get("phone"):
            pol_sms = f"🚨 RED ALERT: Accident reported near {primary_police['name']} ({primary_police['distance_km']} km). Open Police Portal: {police_portal_link}"
            send_real_sms("Police", [primary_police["phone"]], pol_sms)

        if ranked_hospitals:
            background_tasks.add_task(process_hospital_auto_cascade, doc_id, user_name, maps_link, data.latitude, data.longitude)
        return {"success": True, "message": "Dispatched", "request_id": doc_id}
    except Exception as e:
        return {"success": False, "message": str(e)}

@router.get("/hospital-portal/{request_id}", response_class=HTMLResponse)
def hospital_portal(request_id: str, attempt: int = 0):
    doc = firestore_get("emergency_requests", request_id)
    if not doc:
        return HTMLResponse("<h2 style='color:white;background:#121212;text-align:center;padding:50px;'>Emergency Request Not Found</h2>", status_code=404)
    req = parse_doc(doc)
    lat = req.get('latitude', 9.1724)
    lon = req.get('longitude', 77.8682)
    ranked = get_ranked_hospitals(lat, lon, attempt)
    if attempt >= len(ranked):
        attempt = 0
    current_hosp = ranked[attempt]
    hosp_lat = current_hosp.get("latitude", lat + 0.02)
    hosp_lon = current_hosp.get("longitude", lon + 0.02)
    is_accepted = 1 if req.get("hospital_status") == "ACCEPTED" else 0
    current_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Hospital Live Tracking Portal</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
            body {{ background-color: #0b0f19; color: #f3f4f6; display: flex; height: 100vh; overflow: hidden; }}
            .sidebar {{ width: 260px; background: #111827; border-right: 1px solid #1f2937; display: flex; flex-direction: column; justify-content: space-between; padding: 20px; }}
            .logo-area {{ font-weight: 700; font-size: 16px; color: #fff; margin-bottom: 25px; }}
            .logo-area span {{ color: #ef4444; }}
            .nav-links {{ display: flex; flex-direction: column; gap: 6px; }}
            .nav-item {{ padding: 10px 14px; border-radius: 8px; color: #9ca3af; text-decoration: none; font-size: 13px; font-weight: 500; }}
            .nav-item.active {{ background: #1f2937; color: #fff; }}
            .main-content {{ flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 20px 25px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .status-badge {{ background: #065f46; color: #34d399; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
            .dashboard-grid {{ display: grid; grid-template-columns: 1fr 380px; gap: 20px; }}
            .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 18px; position: relative; }}
            .alert-box {{ border: 1px solid #7f1d1d; background: linear-gradient(135deg, #111827 0%, #1f1115 100%); }}
            .red-badge {{ background: #7f1d1d; color: #f87171; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; }}
            #map {{ height: 320px; border-radius: 10px; border: 1px solid #1f2937; margin-top: 15px; z-index: 1; background: #0b0f19; }}
            .leaflet-tile-pane {{ filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }}
            .detail-row {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #1f2937; color: #9ca3af; }}
            .detail-row span:last-child {{ color: #f3f4f6; font-weight: 500; text-align: right; }}
            .btn {{ display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px; border-radius: 8px; font-weight: 700; text-decoration: none; cursor: pointer; border: none; font-size: 12px; margin-top: 12px; }}
            .btn-accept {{ background: #059669; color: white; }}
            .btn-accept:hover {{ background: #047857; }}
            .btn-busy {{ background: #dc2626; color: white; }}
            .btn-busy:hover {{ background: #b91c1c; }}
            .stats-container {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 18px; }}
            .stat-card {{ background-color: #111827; border: 1px solid #1f2937; padding: 12px; border-radius: 10px; text-align: center; }}
            .stat-num {{ font-size: 20px; font-weight: bold; color: #ffffff; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div>
                <div class="logo-area">🛡️ LifeGuard <span>AI</span></div>
                <div class="nav-links">
                    <a href="#" class="nav-item active">📊 Dashboard</a>
                    <a href="#" class="nav-item">🚨 Active Alerts</a>
                    <a href="#" class="nav-item">🚑 Ambulance Units</a>
                    <a href="#" class="nav-item">⚙️ Settings</a>
                </div>
            </div>
            <div style="font-size: 11px; color: #6b7280;">LifeGuard AI © 2026</div>
        </div>
        <div class="main-content">
            <div class="header">
                <div>
                    <h2 style="font-size: 18px; color: #fff;">Welcome back, {current_hosp['name']} 👨‍⚕️</h2>
                    <p style="font-size: 12px; color: #9ca3af;">Live Tracking & Command Center</p>
                </div>
                <span class="status-badge">🟢 Online</span>
            </div>
            <div class="dashboard-grid">
                <div class="card alert-box">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span class="red-badge">LIVE AMBULANCE TRACKER</span>
                        <span style="font-size: 12px; color: #34d399;" id="tracking-status">Waiting for Dispatch...</span>
                    </div>
                    <h2 style="font-size: 18px; color: #fff; margin-bottom: 4px;">{current_hosp['name']}</h2>
                    <p style="color: #9ca3af; font-size: 12px; margin-bottom: 10px;">Distance: {current_hosp['distance_km']} km away</p>
                    <div id="map"></div>
                </div>
                <div class="card">
                    <h3 style="margin-bottom: 15px; font-size: 15px; color: #fff;">Accident Details</h3>
                    <div class="detail-row"><span>Patient</span><span>Unknown (Critical)</span></div>
                    <div class="detail-row"><span>Coordinates</span><span>{lat}, {lon}</span></div>
                    <div class="detail-row" style="border: none;"><span>Time</span><span>{current_time}</span></div>
                    <hr style="border: 0; border-top: 1px solid #1f2937; margin: 12px 0;">
                    <h3 style="margin-bottom: 8px; font-size: 14px; color: #fff;">Quick Actions</h3>
                    <a href="/hospital-action/{request_id}?attempt={attempt}&action=accept" class="btn btn-accept">✅ ACCEPT & DISPATCH AMBULANCE</a>
                    <a href="/hospital-action/{request_id}?attempt={attempt}&action=decline" class="btn btn-busy">❌ NO BEDS / BUSY (AUTO-REROUTE)</a>
                </div>
            </div>
            <div class="stats-container">
                <div class="stat-card"><div style="color: #f87171; font-size: 11px;">Active Alerts</div><div class="stat-num">3</div></div>
                <div class="stat-card"><div style="color: #34d399; font-size: 11px;">Dispatched</div><div class="stat-num">1</div></div>
                <div class="stat-card"><div style="color: #60a5fa; font-size: 11px;">Units Ready</div><div class="stat-num">5</div></div>
                <div class="stat-card"><div style="color: #f59e0b; font-size: 11px;">Completed</div><div class="stat-num">12</div></div>
                <div class="stat-card"><div style="color: #a78bfa; font-size: 11px;">Avg Time</div><div class="stat-num">4.6 min</div></div>
            </div>
        </div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var accidentLat = {lat};
            var accidentLon = {lon};
            var hospLat = {hosp_lat};
            var hospLon = {hosp_lon};
            var isAccepted = {is_accepted};
            var map = L.map('map').setView([accidentLat, accidentLon], 13);
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19, attribution: '© OpenStreetMap' }}).addTo(map);
            var accidentIcon = L.divIcon({{ html: '🚨', className: 'custom-icon', iconSize: [30, 30] }});
            var ambulanceIcon = L.divIcon({{ html: '🚑', className: 'custom-icon', iconSize: [30, 30] }});
            var accidentMarker = L.marker([accidentLat, accidentLon], {{icon: accidentIcon}}).addTo(map).bindPopup("<b>Accident Spot</b>").openPopup();
            var ambulanceMarker = L.marker([hospLat, hospLon], {{icon: ambulanceIcon}}).addTo(map).bindPopup("<b>Ambulance / Hospital</b>");
            var polyline = L.polyline([[hospLat, hospLon], [accidentLat, accidentLon]], {{color: '#34d399', weight: 4, opacity: 0.8}}).addTo(map);
            if (isAccepted === 1) {{
                document.getElementById('tracking-status').innerText = "🚑 Ambulance En Route (Moving)...";
                document.getElementById('tracking-status').style.color = "#34d399";
                var step = 0;
                var totalSteps = 100;
                var latStep = (accidentLat - hospLat) / totalSteps;
                var lonStep = (accidentLon - hospLon) / totalSteps;
                var interval = setInterval(function() {{
                    if (step >= totalSteps) {{
                        clearInterval(interval);
                        document.getElementById('tracking-status').innerText = "✅ Ambulance Arrived at Spot!";
                        return;
                    }}
                    hospLat += latStep;
                    hospLon += lonStep;
                    ambulanceMarker.setLatLng([hospLat, hospLon]);
                    polyline.setLatLngs([[hospLat, hospLon], [accidentLat, accidentLon]]);
                    step++;
                }}, 200);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/police-portal/{request_id}", response_class=HTMLResponse)
def police_portal(request_id: str, attempt: int = 0):
    doc = firestore_get("emergency_requests", request_id)
    if not doc:
        return HTMLResponse("<h2 style='color:white;background:#121212;text-align:center;padding:50px;'>Request Not Found</h2>", status_code=404)
    req = parse_doc(doc)
    lat = req.get('latitude', 9.1724)
    lon = req.get('longitude', 77.8682)
    ranked = get_ranked_police_stations(lat, lon, attempt)
    if attempt >= len(ranked):
        attempt = 0
    current_pol = ranked[attempt]
    pol_lat = current_pol.get("latitude", lat + 0.015)
    pol_lon = current_pol.get("longitude", lon + 0.015)
    is_accepted = 1 if req.get("police_status") == "ACCEPTED" else 0
    current_time = datetime.now().strftime("%d %b %Y, %I:%M %p")
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Police Live Tracking Portal</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
        <style>
            * {{ box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }}
            body {{ background-color: #0b0f19; color: #f3f4f6; display: flex; height: 100vh; overflow: hidden; }}
            .sidebar {{ width: 260px; background: #111827; border-right: 1px solid #1f2937; display: flex; flex-direction: column; justify-content: space-between; padding: 20px; }}
            .logo-area {{ font-weight: 700; font-size: 16px; color: #fff; margin-bottom: 25px; }}
            .logo-area span {{ color: #8b5cf6; }}
            .nav-links {{ display: flex; flex-direction: column; gap: 6px; }}
            .nav-item {{ padding: 10px 14px; border-radius: 8px; color: #9ca3af; text-decoration: none; font-size: 13px; font-weight: 500; }}
            .nav-item.active {{ background: #1f2937; color: #fff; }}
            .main-content {{ flex: 1; display: flex; flex-direction: column; overflow-y: auto; padding: 20px 25px; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .status-badge {{ background: #312e81; color: #a78bfa; padding: 5px 12px; border-radius: 20px; font-size: 11px; font-weight: 700; }}
            .dashboard-grid {{ display: grid; grid-template-columns: 1fr 380px; gap: 20px; }}
            .card {{ background: #111827; border: 1px solid #1f2937; border-radius: 12px; padding: 18px; position: relative; }}
            .alert-box {{ border: 1px solid #5b21b6; background: linear-gradient(135deg, #111827 0%, #1a1128 100%); }}
            .purple-badge {{ background: #5b21b6; color: #c4b5fd; padding: 3px 8px; border-radius: 6px; font-size: 10px; font-weight: 700; }}
            #map {{ height: 320px; border-radius: 10px; border: 1px solid #1f2937; margin-top: 15px; z-index: 1; background: #0b0f19; }}
            .leaflet-tile-pane {{ filter: invert(100%) hue-rotate(180deg) brightness(95%) contrast(90%); }}
            .detail-row {{ display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid #1f2937; color: #9ca3af; }}
            .detail-row span:last-child {{ color: #f3f4f6; font-weight: 500; text-align: right; }}
            .btn {{ display: flex; align-items: center; justify-content: center; gap: 8px; width: 100%; padding: 12px; border-radius: 8px; font-weight: 700; text-decoration: none; cursor: pointer; border: none; font-size: 12px; margin-top: 12px; }}
            .btn-accept {{ background: #7c3aed; color: white; }}
            .btn-accept:hover {{ background: #6d28d9; }}
            .btn-busy {{ background: #dc2626; color: white; }}
            .btn-busy:hover {{ background: #b91c1c; }}
            .stats-container {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-top: 18px; }}
            .stat-card {{ background-color: #111827; border: 1px solid #1f2937; padding: 12px; border-radius: 10px; text-align: center; }}
            .stat-num {{ font-size: 20px; font-weight: bold; color: #ffffff; margin-top: 4px; }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div>
                <div class="logo-area">🛡️ LifeGuard <span>AI</span></div>
                <div class="nav-links">
                    <a href="#" class="nav-item active">📊 Dashboard</a>
                    <a href="#" class="nav-item">🚨 Active Alerts</a>
                    <a href="#" class="nav-item">👮 Patrol Units</a>
                    <a href="#" class="nav-item">⚙️ Settings</a>
                </div>
            </div>
            <div style="font-size: 11px; color: #6b7280;">LifeGuard AI © 2026</div>
        </div>
        <div class="main-content">
            <div class="header">
                <div>
                    <h2 style="font-size: 18px; color: #fff;">Welcome back, {current_pol['name']} 👮</h2>
                    <p style="font-size: 12px; color: #9ca3af;">Live Tracking & Command Center</p>
                </div>
                <span class="status-badge">🟢 Online</span>
            </div>
            <div class="dashboard-grid">
                <div class="card alert-box">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                        <span class="purple-badge">LIVE PATROL TRACKER</span>
                        <span style="font-size: 12px; color: #a78bfa;" id="tracking-status">Waiting for Deployment...</span>
                    </div>
                    <h2 style="font-size: 18px; color: #fff; margin-bottom: 4px;">{current_pol['name']}</h2>
                    <p style="color: #9ca3af; font-size: 12px; margin-bottom: 10px;">Distance: {current_pol['distance_km']} km away</p>
                    <div id="map"></div>
                </div>
                <div class="card">
                    <h3 style="margin-bottom: 15px; font-size: 15px; color: #fff;">Incident Details</h3>
                    <div class="detail-row"><span>Type</span><span>Two Wheeler Accident</span></div>
                    <div class="detail-row"><span>Coordinates</span><span>{lat}, {lon}</span></div>
                    <div class="detail-row" style="border: none;"><span>Time</span><span>{current_time}</span></div>
                    <hr style="border: 0; border-top: 1px solid #1f2937; margin: 12px 0;">
                    <h3 style="margin-bottom: 8px; font-size: 14px; color: #fff;">Quick Actions</h3>
                    <a href="/police-action/{request_id}?attempt={attempt}&action=accept" class="btn btn-accept">✅ ACCEPT & DEPLOY PATROL</a>
                    <a href="/police-action/{request_id}?attempt={attempt}&action=decline" class="btn btn-busy">❌ BUSY / REDIRECT NEXT STATION</a>
                </div>
            </div>
            <div class="stats-container">
                <div class="stat-card"><div style="color: #f87171; font-size: 11px;">Active Alerts</div><div class="stat-num">4</div></div>
                <div class="stat-card"><div style="color: #34d399; font-size: 11px;">Deployed</div><div class="stat-num">2</div></div>
                <div class="stat-card"><div style="color: #60a5fa; font-size: 11px;">Available</div><div class="stat-num">7</div></div>
                <div class="stat-card"><div style="color: #f59e0b; font-size: 11px;">Completed</div><div class="stat-num">15</div></div>
                <div class="stat-card"><div style="color: #a78bfa; font-size: 11px;">Avg Time</div><div class="stat-num">4.2 min</div></div>
            </div>
        </div>
        <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
        <script>
            var accidentLat = {lat};
            var accidentLon = {lon};
            var polLat = {pol_lat};
            var polLon = {pol_lon};
            var isAccepted = {is_accepted};
            var map = L.map('map').setView([accidentLat, accidentLon], 13);
            L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{ maxZoom: 19, attribution: '© OpenStreetMap' }}).addTo(map);
            var accidentIcon = L.divIcon({{ html: '🚨', className: 'custom-icon', iconSize: [30, 30] }});
            var policeIcon = L.divIcon({{ html: '🚓', className: 'custom-icon', iconSize: [30, 30] }});
            var accidentMarker = L.marker([accidentLat, accidentLon], {{icon: accidentIcon}}).addTo(map).bindPopup("<b>Accident Spot</b>").openPopup();
            var policeMarker = L.marker([polLat, polLon], {{icon: policeIcon}}).addTo(map).bindPopup("<b>Police Station</b>");
            var polyline = L.polyline([[polLat, polLon], [accidentLat, accidentLon]], {{color: '#a78bfa', weight: 4, opacity: 0.8}}).addTo(map);
            if (isAccepted === 1) {{
                document.getElementById('tracking-status').innerText = "🚓 Patrol Unit En Route (Moving)...";
                document.getElementById('tracking-status').style.color = "#a78bfa";
                var step = 0;
                var totalSteps = 100;
                var latStep = (accidentLat - polLat) / totalSteps;
                var lonStep = (accidentLon - polLon) / totalSteps;
                var interval = setInterval(function() {{
                    if (step >= totalSteps) {{
                        clearInterval(interval);
                        document.getElementById('tracking-status').innerText = "✅ Patrol Unit Arrived at Spot!";
                        return;
                    }}
                    polLat += latStep;
                    polLon += lonStep;
                    policeMarker.setLatLng([polLat, polLon]);
                    polyline.setLatLngs([[polLat, polLon], [accidentLat, accidentLon]]);
                    step++;
                }}, 200);
            }}
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/hospital-action/{doc_id}")
def handle_hospital_action(doc_id: str, attempt: int = 0, action: str = "accept"):
    try:
        doc = firestore_get("emergency_requests", doc_id)
        if not doc:
            return {"detail": "Not Found"}
            
        data = parse_doc(doc)
        lat = data.get("latitude")
        lng = data.get("longitude")
        
        if action.lower() == "accept":
            firestore_patch("emergency_requests", doc_id, {
                "hospital_status": "ACCEPTED",
                "status": "ACCEPTED"
            })
            return {"status": "success", "message": "Hospital Accepted"}
        else:
            next_attempt = attempt + 1
            hospitals = get_ranked_hospitals(lat, lng, attempt=next_attempt)
            next_hosp = hospitals[0] if hospitals else {}
            
            firestore_patch("emergency_requests", doc_id, {
                "hospital_status": "DISPATCHED",
                "hospital_name": next_hosp.get("name", "Alternative Hospital")
            })
            
            return RedirectResponse(url=f"/hospital-portal/{doc_id}?attempt={next_attempt}", status_code=303)
            
    except Exception as e:
        return {"detail": str(e)}

@router.get("/police-action/{doc_id}")
def handle_police_action(doc_id: str, attempt: int = 0, action: str = "accept"):
    try:
        doc = firestore_get("emergency_requests", doc_id)
        if not doc:
            return {"detail": "Not Found"}
            
        data = parse_doc(doc)
        lat = data.get("latitude")
        lng = data.get("longitude")
        
        if action.lower() == "accept":
            firestore_patch("emergency_requests", doc_id, {
                "police_status": "ACCEPTED"
            })
            return {"status": "success", "message": "Police Accepted"}
        else:
            next_attempt = attempt + 1
            police_stations = get_ranked_police_stations(lat, lng, attempt=next_attempt)
            next_pol = police_stations[0] if police_stations else {}
            
            firestore_patch("emergency_requests", doc_id, {
                "police_status": "ALERTED",
                "police_name": next_pol.get("name", "Alternative Police Station")
            })
            
            return RedirectResponse(url=f"/police-portal/{doc_id}?attempt={next_attempt}", status_code=303)
            
    except Exception as e:
        return {"detail": str(e)}