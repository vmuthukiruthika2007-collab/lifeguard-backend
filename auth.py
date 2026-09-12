import os
import shutil
import requests
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from passlib.context import CryptContext

router = APIRouter()

PROJECT_ID = "lifeguard-ai-1dff7"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ================= FIRESTORE REST API HELPERS =================

def firestore_get(collection_path: str, doc_id: str = ""):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}" + (f"/{doc_id}" if doc_id else "")
    try:
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Firestore GET Error ({collection_path}): {e}")
    return None

def firestore_set(collection_path: str, doc_id: str, fields: dict):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}/{doc_id}"
    formatted_fields = {}
    for k, v in fields.items():
        if v is None:
            continue
        elif isinstance(v, bool):
            formatted_fields[k] = {"booleanValue": v}
        elif isinstance(v, (int, float)):
            formatted_fields[k] = {"integerValue": str(int(v))} if isinstance(v, int) else {"doubleValue": float(v)}
        else:
            formatted_fields[k] = {"stringValue": str(v)}

    try:
        res = requests.patch(url, json={"fields": formatted_fields}, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"Firestore SET Error ({collection_path}): {e}")
        return False

def firestore_post(collection_path: str, fields: dict):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}"
    formatted_fields = {}
    for k, v in fields.items():
        if v is None:
            continue
        elif isinstance(v, bool):
            formatted_fields[k] = {"booleanValue": v}
        elif isinstance(v, (int, float)):
            formatted_fields[k] = {"integerValue": str(int(v))} if isinstance(v, int) else {"doubleValue": float(v)}
        else:
            formatted_fields[k] = {"stringValue": str(v)}

    try:
        res = requests.post(url, json={"fields": formatted_fields}, timeout=5)
        if res.status_code == 200:
            doc_name = res.json().get("name", "")
            return doc_name.split("/")[-1]
    except Exception as e:
        print(f"Firestore POST Error ({collection_path}): {e}")
    return None

def firestore_delete(collection_path: str, doc_id: str):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}/{doc_id}"
    try:
        res = requests.delete(url, timeout=5)
        return res.status_code == 200
    except Exception as e:
        print(f"Firestore DELETE Error ({collection_path}): {e}")
        return False

def parse_doc(doc: dict):
    data = {}
    fields = doc.get("fields", {})
    for k, v in fields.items():
        if "stringValue" in v:
            data[k] = v["stringValue"]
        elif "integerValue" in v:
            data[k] = int(v["integerValue"])
        elif "doubleValue" in v:
            data[k] = float(v["doubleValue"])
        elif "booleanValue" in v:
            data[k] = v["booleanValue"]
    data["id"] = doc.get("name", "").split("/")[-1]
    return data


# ================= MODELS =================

class RegisterUser(BaseModel):
    name: str
    phone: str
    email: str
    blood_group: str
    password: str

class LoginUser(BaseModel):
    email: str
    password: str

class UpdateProfile(BaseModel):
    name: str
    phone: str
    email: str
    blood_group: str

class ChangePassword(BaseModel):
    user_id: int
    old_password: str
    new_password: str

class EmergencyContactCreate(BaseModel):
    user_id: int
    name: str
    phone: str
    relationship: str
    email: Optional[str] = None
    image_path: Optional[str] = None

class EmergencyContactUpdate(BaseModel):
    contact_id: str
    user_id: Optional[int] = None
    name: str
    phone: str
    relationship: str
    email: Optional[str] = None
    image_path: Optional[str] = None

class UserSettings(BaseModel):
    user_id: int
    crash_detection: bool = True
    sms_alert: bool = True
    sound_vibration: bool = True
    auto_call: bool = True


# ================= REGISTER =================

@router.post("/register")
def register(user: RegisterUser):
    try:
        users_res = firestore_get("users")
        if users_res and "documents" in users_res:
            for doc in users_res["documents"]:
                data = parse_doc(doc)
                if data.get("email", "").lower() == user.email.strip().lower():
                    return {"success": False, "message": "Email already registered"}

        user_id = int(datetime.utcnow().timestamp())
        hashed_password = pwd_context.hash(user.password)

        user_data = {
            "user_id": user_id,
            "name": user.name.strip(),
            "phone": user.phone.strip(),
            "email": user.email.strip(),
            "blood_group": user.blood_group.strip(),
            "password": hashed_password,
            "created_at": datetime.utcnow().isoformat(),
        }

        success = firestore_set("users", str(user_id), user_data)
        if success:
            return {"success": True, "message": "Registration Successful", "user_id": user_id}
        return {"success": False, "message": "Failed to create user record in Firestore"}

    except Exception as e:
        print("REGISTER ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= LOGIN =================

@router.post("/login")
def login(user: LoginUser):
    try:
        users_res = firestore_get("users")
        if not users_res or "documents" not in users_res:
            return {"success": False, "message": "Email not found"}

        found_user = None
        for doc in users_res["documents"]:
            data = parse_doc(doc)
            if data.get("email", "").lower() == user.email.strip().lower():
                found_user = data
                break

        if not found_user:
            return {"success": False, "message": "Email not found"}

        if not pwd_context.verify(user.password, found_user.get("password", "")):
            return {"success": False, "message": "Incorrect password"}

        return {
            "success": True,
            "message": "Login Successful",
            "user": {
                "id": found_user.get("user_id", found_user.get("id")),
                "name": found_user.get("name"),
                "email": found_user.get("email"),
                "phone": found_user.get("phone"),
                "blood_group": found_user.get("blood_group"),
                "profile_image": found_user.get("profile_image"),
            },
        }

    except Exception as e:
        print("LOGIN ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= GET PROFILE =================

@router.get("/profile/{user_id}")
def get_profile(user_id: int):
    try:
        doc = firestore_get("users", str(user_id))
        if not doc:
            return {"success": False, "message": "User not found"}

        user = parse_doc(doc)
        return {
            "success": True,
            "user": {
                "id": user.get("user_id", user_id),
                "name": user.get("name"),
                "phone": user.get("phone"),
                "email": user.get("email"),
                "blood_group": user.get("blood_group"),
                "profile_image": user.get("profile_image"),
            },
        }

    except Exception as e:
        print("GET PROFILE ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= UPDATE PROFILE =================

@router.put("/profile/{user_id}")
def update_profile(user_id: int, user: UpdateProfile):
    try:
        success = firestore_set("users", str(user_id), {
            "name": user.name.strip(),
            "phone": user.phone.strip(),
            "email": user.email.strip(),
            "blood_group": user.blood_group.strip(),
        })

        if success:
            return {"success": True, "message": "Profile Updated Successfully"}
        return {"success": False, "message": "Failed to update profile"}

    except Exception as e:
        print("UPDATE PROFILE ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= CHANGE PASSWORD =================

@router.post("/change-password/{user_id}")
def change_password(user_id: int, req: ChangePassword):
    try:
        doc = firestore_get("users", str(user_id))
        if not doc:
            return {"success": False, "message": "User not found"}

        user_data = parse_doc(doc)
        if not pwd_context.verify(req.old_password, user_data.get("password", "")):
            return {"success": False, "message": "Current password is incorrect"}

        new_hashed = pwd_context.hash(req.new_password)
        success = firestore_set("users", str(user_id), {"password": new_hashed})

        if success:
            return {"success": True, "message": "Password updated successfully"}
        return {"success": False, "message": "Failed to update password"}

    except Exception as e:
        print("CHANGE PASSWORD ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= UPLOAD PROFILE IMAGE =================

@router.post("/upload-profile-image/{user_id}")
def upload_profile_image(user_id: int, file: UploadFile = File(...)):
    try:
        file_ext = os.path.splitext(file.filename)[1]
        saved_filename = f"user_{user_id}{file_ext}"
        file_location = os.path.join(UPLOAD_DIR, saved_filename)

        with open(file_location, "wb+") as buffer:
            shutil.copyfileobj(file.file, buffer)

        image_url = f"/static/uploads/{saved_filename}"
        firestore_set("users", str(user_id), {"profile_image": image_url})

        return {
            "success": True,
            "message": "Profile image uploaded successfully",
            "image_url": image_url,
        }

    except Exception as e:
        print("UPLOAD IMAGE ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= EMERGENCY CONTACTS CRUD =================

@router.get("/contacts/{user_id}")
def get_emergency_contacts(user_id: int):
    try:
        contacts_res = firestore_get(f"users/{user_id}/contacts")
        contact_list = []
        if contacts_res and "documents" in contacts_res:
            for doc in contacts_res["documents"]:
                data = parse_doc(doc)
                contact_list.append({
                    "contact_id": data.get("id"),
                    "user_id": user_id,
                    "name": data.get("name"),
                    "phone": data.get("phone"),
                    "relationship": data.get("relationship"),
                    "email": data.get("email"),
                    "image_path": data.get("image_path"),
                })
        return {"success": True, "contacts": contact_list}

    except Exception as e:
        print("GET CONTACTS ERROR:", e)
        return {"success": False, "contacts": [], "message": str(e)}

@router.post("/contacts/add")
def add_emergency_contact(contact: EmergencyContactCreate):
    try:
        doc_id = firestore_post(f"users/{contact.user_id}/contacts", {
            "name": contact.name.strip(),
            "phone": contact.phone.strip(),
            "relationship": contact.relationship.strip(),
            "email": contact.email or "",
            "image_path": contact.image_path or "",
            "created_at": datetime.utcnow().isoformat(),
        })

        if doc_id:
            return {"success": True, "message": "Emergency Contact Added Successfully", "contact_id": doc_id}
        return {"success": False, "message": "Failed to add emergency contact"}

    except Exception as e:
        print("ADD CONTACT ERROR:", e)
        return {"success": False, "message": str(e)}

@router.put("/contacts/update")
def update_emergency_contact(contact: EmergencyContactUpdate):
    try:
        target_path = f"users/{contact.user_id}/contacts" if contact.user_id else None
        fields = {
            "name": contact.name.strip(),
            "phone": contact.phone.strip(),
            "relationship": contact.relationship.strip(),
            "email": contact.email or "",
            "image_path": contact.image_path or "",
        }

        if target_path:
            success = firestore_set(target_path, contact.contact_id, fields)
            if success:
                return {"success": True, "message": "Emergency Contact Updated Successfully"}

        return {"success": False, "message": "Update failed: user_id is required"}

    except Exception as e:
        print("UPDATE CONTACT ERROR:", e)
        return {"success": False, "message": str(e)}

@router.delete("/contacts/delete/{contact_id}")
def delete_emergency_contact(contact_id: str, user_id: Optional[int] = 1):
    try:
        success = firestore_delete(f"users/{user_id}/contacts", contact_id)
        if success:
            return {"success": True, "message": "Emergency Contact Deleted Successfully"}
        return {"success": False, "message": "Failed to delete contact"}

    except Exception as e:
        print("DELETE CONTACT ERROR:", e)
        return {"success": False, "message": str(e)}


# ================= USER SETTINGS =================

@router.get("/settings/{user_id}")
def get_user_settings(user_id: int):
    try:
        doc = firestore_get("settings", str(user_id))
        if doc:
            settings_data = parse_doc(doc)
            return {"success": True, "settings": settings_data}

        default_settings = {
            "user_id": user_id,
            "crash_detection": True,
            "sms_alert": True,
            "sound_vibration": True,
            "auto_call": True,
        }
        firestore_set("settings", str(user_id), default_settings)
        return {"success": True, "settings": default_settings}

    except Exception as e:
        print("GET SETTINGS ERROR:", e)
        return {"success": False, "message": str(e)}

@router.post("/settings/update")
def update_user_settings(data: UserSettings):
    try:
        settings_dict = {
            "user_id": data.user_id,
            "crash_detection": data.crash_detection,
            "sms_alert": data.sms_alert,
            "sound_vibration": data.sound_vibration,
            "auto_call": data.auto_call,
        }
        firestore_set("settings", str(data.user_id), settings_dict)
        return {"success": True, "message": "Preferences saved to Firestore successfully"}

    except Exception as e:
        print("UPDATE SETTINGS ERROR:", e)
        return {"success": False, "message": str(e)}