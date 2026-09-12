import requests
from typing import Optional
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

PROJECT_ID = "lifeguard-ai-1dff7"
FIRESTORE_BASE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"


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

class ContactModel(BaseModel):
    name: str
    phone: str
    relationship: str
    email: Optional[str] = ""
    image_path: Optional[str] = ""


class UpdateContactModel(BaseModel):
    name: str
    phone: str
    relationship: str
    email: Optional[str] = ""
    image_path: Optional[str] = ""
    user_id: Optional[int] = 1


# ================= ADD CONTACT =================

@router.post("/contacts/{user_id}")
def add_contact(user_id: int, contact: ContactModel):
    try:
        doc_id = firestore_post(f"users/{user_id}/contacts", {
            "name": contact.name.strip(),
            "phone": contact.phone.strip(),
            "relationship": contact.relationship.strip(),
            "email": contact.email or "",
            "image_path": contact.image_path or "",
            "created_at": datetime.utcnow().isoformat(),
        })

        if doc_id:
            return {
                "success": True,
                "message": "Contact Added Successfully",
                "contact_id": doc_id,
            }

        return {
            "success": False,
            "message": "Failed to add contact in Firestore",
        }

    except Exception as e:
        print("ADD CONTACT ERROR:", e)
        return {
            "success": False,
            "message": str(e),
        }


# ================= GET CONTACTS =================

@router.get("/contacts/{user_id}")
def get_contacts(user_id: int):
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
                    "email": data.get("email", ""),
                    "image_path": data.get("image_path", ""),
                })

        return {
            "success": True,
            "contacts": contact_list,
        }

    except Exception as e:
        print("GET CONTACTS ERROR:", e)
        return {
            "success": False,
            "contacts": [],
            "message": str(e),
        }


# ================= UPDATE CONTACT =================

@router.put("/contacts/{contact_id}")
def update_contact(contact_id: str, contact: UpdateContactModel):
    try:
        user_id = contact.user_id or 1
        success = firestore_set(f"users/{user_id}/contacts", contact_id, {
            "name": contact.name.strip(),
            "phone": contact.phone.strip(),
            "relationship": contact.relationship.strip(),
            "email": contact.email or "",
            "image_path": contact.image_path or "",
        })

        if success:
            return {
                "success": True,
                "message": "Contact Updated Successfully",
            }

        return {
            "success": False,
            "message": "Failed to update contact in Firestore",
        }

    except Exception as e:
        print("UPDATE CONTACT ERROR:", e)
        return {
            "success": False,
            "message": str(e),
        }


# ================= DELETE CONTACT =================

@router.delete("/contacts/{contact_id}")
def delete_contact(contact_id: str, user_id: Optional[int] = 1):
    try:
        success = firestore_delete(f"users/{user_id}/contacts", contact_id)

        if success:
            return {
                "success": True,
                "message": "Contact Deleted Successfully",
            }

        return {
            "success": False,
            "message": "Failed to delete contact from Firestore",
        }

    except Exception as e:
        print("DELETE CONTACT ERROR:", e)
        return {
            "success": False,
            "message": str(e),
        }