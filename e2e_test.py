import sys
import uuid
import time
from fastapi.testclient import TestClient

print("==================================================")
print("[STARTING MOODYTRIPS END-TO-END (E2E) TEST SUITE]")
print("==================================================")

try:
    from app import app
    client = TestClient(app)
    print("[+] App loaded successfully into TestClient.")
except Exception as e:
    print(f"[-] Failed to load app: {e}")
    sys.exit(1)

test_email = f"testuser_{uuid.uuid4().hex[:6]}@example.com"
test_password = "password123"
auth_headers = {}
created_thread_id = None

# Step 1: Health Check Endpoint
print("\n--- [1/6] Testing Health Endpoint (/health) ---")
res = client.get("/health")
assert res.status_code == 200, f"Expected 200, got {res.status_code}"
assert res.json().get("status") == "ok"
print(f"[PASS] /health returned status: {res.json()}")

# Step 2: Register New User
print("\n--- [2/6] Testing User Registration (/api/auth/register) ---")
res = client.post("/api/auth/register", json={"email": test_email, "password": test_password})
assert res.status_code == 200, f"Registration failed with code {res.status_code}: {res.text}"
data = res.json()
assert data.get("success") is True, f"Registration success false: {data}"
assert "token" in data, "Token missing in registration response"
token = data["token"]
auth_headers = {"Authorization": f"Bearer {token}"}
print(f"[PASS] User registered successfully. Email: {test_email}")

# Step 3: User Login
print("\n--- [3/6] Testing User Login (/api/auth/login) ---")
res = client.post("/api/auth/login", json={"email": test_email, "password": test_password})
assert res.status_code == 200, f"Login failed with code {res.status_code}: {res.text}"
data = res.json()
assert data.get("success") is True, f"Login success false: {data}"
print("[PASS] Login authentication successful.")

# Step 4: Verify Token Authentication (/api/auth/me)
print("\n--- [4/6] Testing Auth Verification Endpoint (/api/auth/me) ---")
res = client.get("/api/auth/me", headers=auth_headers)
assert res.status_code == 200, f"Auth verify failed: {res.text}"
data = res.json()
assert data["user"]["email"] == test_email
print(f"[PASS] JWT Token validated for user: {data['user']['email']}")

# Step 5: Chat Management APIs
print("\n--- [5/6] Testing Chat Management (/api/chats) ---")
# List initial chats (should be empty)
res = client.get("/api/chats", headers=auth_headers)
assert res.status_code == 200
assert len(res.json()["chats"]) == 0
print("[PASS] Initial user chats retrieved (0 existing chats).")

# Create a new chat session
res = client.post("/api/chats", json={"title": "Goa Weekend Trip"}, headers=auth_headers)
assert res.status_code == 200, f"Create chat failed ({res.status_code}): {res.text}"
chat_info = res.json()["chat"]
created_thread_id = chat_info["thread_id"]
print(f"[PASS] Created chat thread ID: {created_thread_id} with title: '{chat_info['title']}'")


# Step 6: Travel AI Planner Endpoint (Full LangGraph Multi-Agent Invocation)
print("\n--- [6/6] Testing Travel AI Multi-Agent Planner (/api/travel) ---")
start_time = time.time()
travel_payload = {
    "message": "Plan a 3 day budget trip from Delhi to Goa under 15000 INR starting 2026-10-10",
    "thread_id": created_thread_id
}
print(f"Sending request: '{travel_payload['message']}'...")
res = client.post("/api/travel", json=travel_payload, headers=auth_headers, timeout=120.0)
duration = time.time() - start_time

assert res.status_code == 200, f"Travel request failed: {res.status_code} - {res.text}"
travel_data = res.json()
assert travel_data.get("success") is True
assert len(travel_data.get("answer", "")) > 100
assert travel_data.get("llm_calls", 0) >= 1

print(f"[PASS] Travel agent responded successfully in {duration:.2f} seconds!")
print(f"Total Agent LLM Calls Executed: {travel_data.get('llm_calls')}")
print(f"Answer Preview (first 250 chars):\n{travel_data['answer'][:250]}...\n")

# Verify Chat History Persistence in DB
res = client.get(f"/api/chats/{created_thread_id}", headers=auth_headers)
assert res.status_code == 200
history = res.json()["messages"]
assert len(history) >= 2  # 1 user message + 1 assistant response
print(f"[PASS] Chat history persisted in database ({len(history)} messages verified).")

print("==================================================")
print("[ALL END-TO-END (E2E) TESTS PASSED SUCCESSFULLY!]")
print("==================================================")

