import requests

# ================= FIRESTORE CLOUD DATABASE CONFIG =================
PROJECT_ID = "lifeguard-ai-1dff7"
FIRESTORE_URL = f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/(default)/documents"

def get_connection():
    """
    Checks real-time connectivity to Firebase Cloud Firestore.
    Replaces legacy MySQL connection.
    """
    try:
        response = requests.get(FIRESTORE_URL, timeout=5)
        if response.status_code == 200:
            print("✅ Firebase Cloud Firestore Connected Successfully!")
            return True
        else:
            print(f"⚠️ Firestore Warning: Received HTTP {response.status_code}")
            return False
    except requests.exceptions.RequestException as err:
        print("❌ Cloud Firestore Connection Error:", err)
        return False

# Self-test when executing `python db.py` directly
if __name__ == "__main__":
    get_connection()