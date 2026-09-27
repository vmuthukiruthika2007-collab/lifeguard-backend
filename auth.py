import os
import shutil
import requests
import random
from typing import Optional
from datetime import datetime, timedelta

from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel
from passlib.context import CryptContext


router = APIRouter()


# ============================================================
# FIRESTORE CONFIGURATION
# ============================================================

PROJECT_ID = "lifeguard-ai-1dff7"

FIRESTORE_BASE_URL = (
    f"https://firestore.googleapis.com/v1/projects/"
    f"{PROJECT_ID}/databases/(default)/documents"
)


# ============================================================
# PASSWORD HASHING
# ============================================================

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


# ============================================================
# PROFILE IMAGE UPLOAD
# ============================================================

UPLOAD_DIR = "static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================================
# FIRESTORE REST API HELPERS
# ============================================================

def firestore_get(collection_path: str, doc_id: str = ""):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}"

    if doc_id:
        url += f"/{doc_id}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()

        print(
            f"Firestore GET failed: "
            f"{response.status_code} - {response.text}"
        )

    except Exception as e:
        print(f"Firestore GET Error ({collection_path}): {e}")

    return None


def firestore_set(
    collection_path: str,
    doc_id: str,
    fields: dict,
    use_mask: bool = True
):
    url = f"{FIRESTORE_BASE_URL}/{collection_path}/{doc_id}"

    if use_mask and fields:
        mask_params = "&".join(
            [
                f"updateMask.fieldPaths={k}"
                for k in fields.keys()
            ]
        )
        url += f"?{mask_params}"

    formatted_fields = {}

    for key, value in fields.items():

        if value is None:
            continue

        if isinstance(value, bool):
            formatted_fields[key] = {
                "booleanValue": value
            }

        elif isinstance(value, int):
            formatted_fields[key] = {
                "integerValue": str(value)
            }

        elif isinstance(value, float):
            formatted_fields[key] = {
                "doubleValue": value
            }

        else:
            formatted_fields[key] = {
                "stringValue": str(value)
            }

    try:
        response = requests.patch(
            url,
            json={"fields": formatted_fields},
            timeout=10
        )

        if response.status_code == 200:
            return True

        print(
            f"Firestore SET failed: "
            f"{response.status_code} - {response.text}"
        )

    except Exception as e:
        print(f"Firestore SET Error ({collection_path}): {e}")

    return False


def firestore_post(collection_path: str, fields: dict):

    url = f"{FIRESTORE_BASE_URL}/{collection_path}"

    formatted_fields = {}

    for key, value in fields.items():

        if value is None:
            continue

        if isinstance(value, bool):
            formatted_fields[key] = {
                "booleanValue": value
            }

        elif isinstance(value, int):
            formatted_fields[key] = {
                "integerValue": str(value)
            }

        elif isinstance(value, float):
            formatted_fields[key] = {
                "doubleValue": value
            }

        else:
            formatted_fields[key] = {
                "stringValue": str(value)
            }

    try:
        response = requests.post(
            url,
            json={"fields": formatted_fields},
            timeout=10
        )

        if response.status_code == 200:

            document_name = response.json().get(
                "name",
                ""
            )

            return document_name.split("/")[-1]

        print(
            f"Firestore POST failed: "
            f"{response.status_code} - {response.text}"
        )

    except Exception as e:
        print(f"Firestore POST Error ({collection_path}): {e}")

    return None


def firestore_delete(collection_path: str, doc_id: str):

    url = f"{FIRESTORE_BASE_URL}/{collection_path}/{doc_id}"

    try:
        response = requests.delete(
            url,
            timeout=10
        )

        if response.status_code in [200, 204]:
            return True

        print(
            f"Firestore DELETE failed: "
            f"{response.status_code} - {response.text}"
        )

    except Exception as e:
        print(
            f"Firestore DELETE Error "
            f"({collection_path}): {e}"
        )

    return False


def parse_doc(doc: dict):

    data = {}

    fields = doc.get("fields", {})

    for key, value in fields.items():

        if "stringValue" in value:
            data[key] = value["stringValue"]

        elif "integerValue" in value:
            data[key] = int(value["integerValue"])

        elif "doubleValue" in value:
            data[key] = float(value["doubleValue"])

        elif "booleanValue" in value:
            data[key] = value["booleanValue"]

    data["id"] = doc.get(
        "name",
        ""
    ).split("/")[-1]

    return data


# ============================================================
# MODELS
# ============================================================

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


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    otp: str
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
    user_id: int
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


# ============================================================
# REGISTER
# ============================================================

@router.post("/register")
def register(user: RegisterUser):

    try:

        entered_email = user.email.strip().lower()

        users_res = firestore_get("users")

        if users_res and "documents" in users_res:

            for doc in users_res["documents"]:

                data = parse_doc(doc)

                existing_email = (
                    data.get("email", "")
                    .strip()
                    .lower()
                )

                if existing_email == entered_email:

                    return {
                        "success": False,
                        "message": "Email already registered"
                    }

        # Timestamp based user ID
        user_id = int(
            datetime.utcnow().timestamp()
        )

        hashed_password = pwd_context.hash(
            user.password
        )

        user_data = {
            "user_id": user_id,
            "name": user.name.strip(),
            "phone": user.phone.strip(),
            "email": entered_email,
            "blood_group": user.blood_group.strip(),
            "password": hashed_password,
            "created_at": datetime.utcnow().isoformat(),
        }

        success = firestore_set(
            "users",
            str(user_id),
            user_data,
            use_mask=False
        )

        if success:

            return {
                "success": True,
                "message": "Registration Successful",
                "user_id": user_id
            }

        return {
            "success": False,
            "message": "Failed to create user record in Firestore"
        }

    except Exception as e:

        print("REGISTER ERROR:", e)

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# LOGIN
# ============================================================

@router.post("/login")
def login(user: LoginUser):

    try:

        entered_email = (
            user.email
            .strip()
            .lower()
        )

        users_res = firestore_get("users")

        if not users_res or "documents" not in users_res:

            return {
                "success": False,
                "message": "Email not found"
            }

        found_user = None

        for doc in users_res["documents"]:

            data = parse_doc(doc)

            stored_email = (
                data.get("email", "")
                .strip()
                .lower()
            )

            if stored_email == entered_email:

                found_user = data
                break

        if not found_user:

            return {
                "success": False,
                "message": "Email not found"
            }

        stored_password = found_user.get(
            "password",
            ""
        )

        if not stored_password:

            return {
                "success": False,
                "message": "Password not found for this account"
            }

        try:

            password_correct = pwd_context.verify(
                user.password,
                stored_password
            )

        except Exception as password_error:

            print(
                "PASSWORD VERIFY ERROR:",
                password_error
            )

            password_correct = False

        if not password_correct:

            return {
                "success": False,
                "message": "Incorrect password"
            }

        return {
            "success": True,
            "message": "Login Successful",
            "user": {
                "id": found_user.get(
                    "user_id",
                    found_user.get("id")
                ),
                "name": found_user.get("name"),
                "email": found_user.get("email"),
                "phone": found_user.get("phone"),
                "blood_group": found_user.get(
                    "blood_group"
                ),
                "profile_image": found_user.get(
                    "profile_image"
                ),
            },
        }

    except Exception as e:

        print("LOGIN ERROR:", e)

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# FORGOT PASSWORD - SEND OTP
# ============================================================

@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordRequest):

    try:

        entered_email = (
            data.email
            .strip()
            .lower()
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Search only existing registered users.
        # Do NOT create a new user here.
        # ----------------------------------------------------

        users_res = firestore_get("users")

        if not users_res or "documents" not in users_res:

            return {
                "success": False,
                "message": "Email not found"
            }

        found_doc_id = None

        for doc in users_res["documents"]:

            parsed = parse_doc(doc)

            stored_email = (
                parsed.get("email", "")
                .strip()
                .lower()
            )

            if stored_email == entered_email:

                found_doc_id = parsed.get("id")
                break

        # ----------------------------------------------------
        # Email not registered
        # ----------------------------------------------------

        if not found_doc_id:

            return {
                "success": False,
                "message": "Email not found"
            }

        # ----------------------------------------------------
        # Generate 6 digit OTP
        # ----------------------------------------------------

        generated_otp = str(
            random.randint(100000, 999999)
        )

        # ----------------------------------------------------
        # OTP expiry = 10 minutes
        # ----------------------------------------------------

        otp_expiry = (
            datetime.utcnow()
            + timedelta(minutes=10)
        ).isoformat()

        # ----------------------------------------------------
        # Save OTP in SAME user document
        # ----------------------------------------------------

        otp_saved = firestore_set(
            "users",
            str(found_doc_id),
            {
                "reset_otp": generated_otp,
                "reset_otp_expiry": otp_expiry,
            },
            use_mask=False
        )

        if not otp_saved:

            return {
                "success": False,
                "message": "Failed to generate OTP"
            }

        # ----------------------------------------------------
        # Brevo email
        # ----------------------------------------------------

        brevo_url = (
            "https://api.brevo.com/v3/smtp/email"
        )

        api_key = os.getenv(
            "BREVO_API_KEY",
            ""
        )

        if not api_key:

            print(
                "WARNING: BREVO_API_KEY is not configured."
            )

            print(
                f"TEST OTP for {entered_email}: "
                f"{generated_otp}"
            )

            return {
                "success": True,
                "message": "OTP generated successfully"
            }

        payload = {
            "sender": {
                "name": "LifeGuard Support",
                "email": "supportlifeguard@gmail.com"
            },
            "to": [
                {
                    "email": entered_email
                }
            ],
            "subject": "LifeGuard - Password Reset OTP",
            "htmlContent": (
                "<p>Your OTP for password reset is: "
                f"<b>{generated_otp}</b>.</p>"
                "<p>This OTP is valid for 10 minutes.</p>"
                "<p>Do not share this OTP with anyone.</p>"
            )
        }

        headers = {
            "accept": "application/json",
            "api-key": api_key,
            "content-type": "application/json"
        }

        try:

            response = requests.post(
                brevo_url,
                json=payload,
                headers=headers,
                timeout=15
            )

            if response.status_code not in [200, 201]:

                print(
                    "Brevo API Error:",
                    response.status_code,
                    response.text
                )

                return {
                    "success": False,
                    "message": "Failed to send OTP email"
                }

        except Exception as mail_error:

            print(
                "Mail Send Error:",
                mail_error
            )

            return {
                "success": False,
                "message": "Unable to send OTP email"
            }

        return {
            "success": True,
            "message": "OTP sent to your email successfully!"
        }

    except Exception as e:

        print(
            "FORGOT PASSWORD ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# RESET PASSWORD
# ============================================================

@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest):

    try:

        entered_email = (
            data.email
            .strip()
            .lower()
        )

        entered_otp = data.otp.strip()

        # ----------------------------------------------------
        # Find SAME registered user
        # ----------------------------------------------------

        users_res = firestore_get("users")

        if not users_res or "documents" not in users_res:

            return {
                "success": False,
                "message": "Email not found"
            }

        found_doc_id = None
        stored_otp = None
        stored_expiry = None

        for doc in users_res["documents"]:

            parsed = parse_doc(doc)

            stored_email = (
                parsed.get("email", "")
                .strip()
                .lower()
            )

            if stored_email == entered_email:

                found_doc_id = parsed.get("id")
                stored_otp = parsed.get("reset_otp")
                stored_expiry = parsed.get(
                    "reset_otp_expiry"
                )

                break

        # ----------------------------------------------------
        # User not found
        # ----------------------------------------------------

        if not found_doc_id:

            return {
                "success": False,
                "message": "Email not found"
            }

        # ----------------------------------------------------
        # OTP exists?
        # ----------------------------------------------------

        if not stored_otp:

            return {
                "success": False,
                "message": "Invalid or expired OTP"
            }

        # ----------------------------------------------------
        # OTP comparison
        # ----------------------------------------------------

        if str(stored_otp).strip() != entered_otp:

            return {
                "success": False,
                "message": "Invalid OTP"
            }

        # ----------------------------------------------------
        # Check OTP expiry
        # ----------------------------------------------------

        if stored_expiry:

            try:

                expiry_time = datetime.fromisoformat(
                    stored_expiry
                )

                current_time = datetime.utcnow()

                if current_time > expiry_time:

                    # Clear expired OTP
                    firestore_set(
                        "users",
                        str(found_doc_id),
                        {
                            "reset_otp": "",
                            "reset_otp_expiry": "",
                        },
                        use_mask=False
                    )

                    return {
                        "success": False,
                        "message": "OTP expired. Please request a new OTP."
                    }

            except Exception as expiry_error:

                print(
                    "OTP EXPIRY CHECK ERROR:",
                    expiry_error
                )

        # ----------------------------------------------------
        # Hash NEW password
        # ----------------------------------------------------

        new_hashed_password = pwd_context.hash(
            data.new_password
        )

        # ----------------------------------------------------
        # UPDATE SAME USER DOCUMENT
        #
        # This is the important part for your problem.
        # ----------------------------------------------------

        password_updated = firestore_set(
            "users",
            str(found_doc_id),
            {
                "password": new_hashed_password,
                "reset_otp": "",
                "reset_otp_expiry": "",
            },
            use_mask=False
        )

        if not password_updated:

            return {
                "success": False,
                "message": "Failed to update password in database"
            }

        return {
            "success": True,
            "message": "Password reset successfully!"
        }

    except Exception as e:

        print(
            "RESET PASSWORD ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# GET PROFILE
# ============================================================

@router.get("/profile/{user_id}")
def get_profile(user_id: int):

    try:

        doc = firestore_get(
            "users",
            str(user_id)
        )

        if not doc:

            return {
                "success": False,
                "message": "User not found"
            }

        user = parse_doc(doc)

        return {
            "success": True,
            "user": {
                "id": user.get(
                    "user_id",
                    user_id
                ),
                "name": user.get("name"),
                "phone": user.get("phone"),
                "email": user.get("email"),
                "blood_group": user.get(
                    "blood_group"
                ),
                "profile_image": user.get(
                    "profile_image"
                ),
            },
        }

    except Exception as e:

        print(
            "GET PROFILE ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# UPDATE PROFILE
# ============================================================

@router.put("/profile/{user_id}")
def update_profile(
    user_id: int,
    user: UpdateProfile
):

    try:

        success = firestore_set(
            "users",
            str(user_id),
            {
                "name": user.name.strip(),
                "phone": user.phone.strip(),
                "email": user.email.strip().lower(),
                "blood_group": user.blood_group.strip(),
            }
        )

        if success:

            return {
                "success": True,
                "message": "Profile Updated Successfully"
            }

        return {
            "success": False,
            "message": "Failed to update profile"
        }

    except Exception as e:

        print(
            "UPDATE PROFILE ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# CHANGE PASSWORD
# ============================================================

@router.post("/change-password/{user_id}")
def change_password(
    user_id: int,
    req: ChangePassword
):

    try:

        doc = firestore_get(
            "users",
            str(user_id)
        )

        if not doc:

            return {
                "success": False,
                "message": "User not found"
            }

        user_data = parse_doc(doc)

        if not pwd_context.verify(
            req.old_password,
            user_data.get("password", "")
        ):

            return {
                "success": False,
                "message": "Current password is incorrect"
            }

        new_hashed = pwd_context.hash(
            req.new_password
        )

        success = firestore_set(
            "users",
            str(user_id),
            {
                "password": new_hashed
            }
        )

        if success:

            return {
                "success": True,
                "message": "Password updated successfully"
            }

        return {
            "success": False,
            "message": "Failed to update password"
        }

    except Exception as e:

        print(
            "CHANGE PASSWORD ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# UPLOAD PROFILE IMAGE
# ============================================================

@router.post("/upload-profile-image/{user_id}")
def upload_profile_image(
    user_id: int,
    file: UploadFile = File(...)
):

    try:

        file_ext = os.path.splitext(
            file.filename or ""
        )[1]

        saved_filename = (
            f"user_{user_id}{file_ext}"
        )

        file_location = os.path.join(
            UPLOAD_DIR,
            saved_filename
        )

        with open(
            file_location,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                file.file,
                buffer
            )

        image_url = (
            f"/static/uploads/{saved_filename}"
        )

        firestore_set(
            "users",
            str(user_id),
            {
                "profile_image": image_url
            }
        )

        return {
            "success": True,
            "message": "Profile image uploaded successfully",
            "image_url": image_url,
        }

    except Exception as e:

        print(
            "UPLOAD IMAGE ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# EMERGENCY CONTACTS - GET
# ============================================================

@router.get("/contacts/{user_id}")
def get_emergency_contacts(user_id: int):

    try:

        contacts_res = firestore_get(
            f"users/{user_id}/contacts"
        )

        contact_list = []

        if contacts_res and "documents" in contacts_res:

            for doc in contacts_res["documents"]:

                data = parse_doc(doc)

                contact_list.append({
                    "contact_id": data.get("id"),
                    "user_id": user_id,
                    "name": data.get("name"),
                    "phone": data.get("phone"),
                    "relationship": data.get(
                        "relationship"
                    ),
                    "email": data.get("email"),
                    "image_path": data.get(
                        "image_path"
                    ),
                })

        return {
            "success": True,
            "contacts": contact_list
        }

    except Exception as e:

        print(
            "GET CONTACTS ERROR:",
            e
        )

        return {
            "success": False,
            "contacts": [],
            "message": str(e)
        }


# ============================================================
# EMERGENCY CONTACTS - ADD
# ============================================================

@router.post("/contacts/add")
def add_emergency_contact(
    contact: EmergencyContactCreate
):

    try:

        doc_id = firestore_post(
            f"users/{contact.user_id}/contacts",
            {
                "name": contact.name.strip(),
                "phone": contact.phone.strip(),
                "relationship": contact.relationship.strip(),
                "email": contact.email or "",
                "image_path": contact.image_path or "",
                "created_at": datetime.utcnow().isoformat(),
            }
        )

        if doc_id:

            return {
                "success": True,
                "message": "Emergency Contact Added Successfully",
                "contact_id": doc_id
            }

        return {
            "success": False,
            "message": "Failed to add emergency contact"
        }

    except Exception as e:

        print(
            "ADD CONTACT ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# EMERGENCY CONTACTS - UPDATE
# ============================================================

@router.put("/contacts/update")
def update_emergency_contact(
    contact: EmergencyContactUpdate
):

    try:

        target_path = (
            f"users/{contact.user_id}/contacts"
        )

        fields = {
            "name": contact.name.strip(),
            "phone": contact.phone.strip(),
            "relationship": contact.relationship.strip(),
            "email": contact.email or "",
            "image_path": contact.image_path or "",
        }

        success = firestore_set(
            target_path,
            contact.contact_id,
            fields
        )

        if success:

            return {
                "success": True,
                "message": "Emergency Contact Updated Successfully"
            }

        return {
            "success": False,
            "message": "Failed to update emergency contact"
        }

    except Exception as e:

        print(
            "UPDATE CONTACT ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# EMERGENCY CONTACTS - DELETE
# ============================================================

@router.delete("/contacts/delete/{contact_id}")
def delete_emergency_contact(
    contact_id: str,
    user_id: int
):

    try:

        success = firestore_delete(
            f"users/{user_id}/contacts",
            contact_id
        )

        if success:

            return {
                "success": True,
                "message": "Emergency Contact Deleted Successfully"
            }

        return {
            "success": False,
            "message": "Failed to delete contact"
        }

    except Exception as e:

        print(
            "DELETE CONTACT ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# USER SETTINGS - GET
# ============================================================

@router.get("/settings/{user_id}")
def get_user_settings(user_id: int):

    try:

        doc = firestore_get(
            "settings",
            str(user_id)
        )

        if doc:

            settings_data = parse_doc(doc)

            return {
                "success": True,
                "settings": settings_data
            }

        default_settings = {
            "user_id": user_id,
            "crash_detection": True,
            "sms_alert": True,
            "sound_vibration": True,
            "auto_call": True,
        }

        firestore_set(
            "settings",
            str(user_id),
            default_settings
        )

        return {
            "success": True,
            "settings": default_settings
        }

    except Exception as e:

        print(
            "GET SETTINGS ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }


# ============================================================
# USER SETTINGS - UPDATE
# ============================================================

@router.post("/settings/update")
def update_user_settings(
    data: UserSettings
):

    try:

        settings_dict = {
            "user_id": data.user_id,
            "crash_detection": data.crash_detection,
            "sms_alert": data.sms_alert,
            "sound_vibration": data.sound_vibration,
            "auto_call": data.auto_call,
        }

        success = firestore_set(
            "settings",
            str(data.user_id),
            settings_dict
        )

        if success:

            return {
                "success": True,
                "message": "Preferences saved to Firestore successfully"
            }

        return {
            "success": False,
            "message": "Failed to save preferences"
        }

    except Exception as e:

        print(
            "UPDATE SETTINGS ERROR:",
            e
        )

        return {
            "success": False,
            "message": str(e)
        }