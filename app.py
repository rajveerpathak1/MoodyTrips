import os
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
import traceback
import uvicorn
import uuid

# 1. Initialize Database first so database and tables exist before backend.py imports and connects checkpointer
from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    create_chat,
    get_user_chats,
    update_chat_title,
    save_chat_message,
    get_chat_messages,
)

print("Initializing MoodyTrips database...")
init_db()

from fastapi import FastAPI, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from auth_utils import hash_password, verify_password, create_access_token, decode_access_token
from backend import run_travel_agent
from tools.flight_tool import find_location_mentions

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="MoodyTrips AI",
    description="LangGraph Multi-Agent Travel Planner with FastAPI Frontend",
    version="1.0.0"
)

app.mount(
    "/static",
    StaticFiles(directory=str(BASE_DIR / "static")),
    name="static"
)

templates = Jinja2Templates(
    directory=str(BASE_DIR / "templates")
)


# =====================================================================
# Auth Security Helper
# =====================================================================

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token is missing or invalid."
        )
    
    token = auth_header.split(" ")[1]
    payload = decode_access_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or signature verification failed."
        )
    
    user = get_user_by_id(payload["user_id"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists in database."
        )
    return user


# =====================================================================
# Pydantic Schemas
# =====================================================================

class RegisterSchema(BaseModel):
    email: str
    password: str

class LoginSchema(BaseModel):
    email: str
    password: str

class TravelRequest(BaseModel):
    message: str
    thread_id: str | None = None

class CreateChatSchema(BaseModel):
    title: str | None = None


# =====================================================================
# Page Route
# =====================================================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={}
    )


# =====================================================================
# Auth Endpoints
# =====================================================================

@app.post("/api/auth/register")
async def register(data: RegisterSchema):
    email = data.email.strip().lower()
    password = data.password
    
    if not email or not password:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Email and password are required."}
        )
    
    if len(password) < 6:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Password must be at least 6 characters."}
        )
    
    existing = get_user_by_email(email)
    if existing:
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Email already registered."}
        )
    
    try:
        pw_hash = hash_password(password)
        new_user = create_user(email, pw_hash)
        
        token = create_access_token({"user_id": new_user["id"], "email": new_user["email"]})
        return {
            "success": True,
            "token": token,
            "user": {
                "id": new_user["id"],
                "email": new_user["email"]
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to register user: {str(e)}"}
        )

@app.post("/api/auth/login")
async def login(data: LoginSchema):
    email = data.email.strip().lower()
    password = data.password
    
    user = get_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Invalid email or password."}
        )
    
    token = create_access_token({"user_id": user["id"], "email": user["email"]})
    return {
        "success": True,
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"]
        }
    }

@app.get("/api/auth/me")
async def get_me(current_user = Depends(get_current_user)):
    return {
        "success": True,
        "user": current_user
    }


# =====================================================================
# Chat Endpoints
# =====================================================================

@app.get("/api/chats")
async def list_chats(current_user = Depends(get_current_user)):
    try:
        chats = get_user_chats(current_user["id"])
        # Format the datetime object to ISO string
        formatted_chats = []
        for chat in chats:
            formatted_chats.append({
                "thread_id": chat["thread_id"],
                "title": chat["title"],
                "created_at": chat["created_at"].isoformat() if chat["created_at"] else None
            })
        return {"success": True, "chats": formatted_chats}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to list chats: {str(e)}"}
        )

@app.post("/api/chats")
async def create_new_chat(data: CreateChatSchema, current_user = Depends(get_current_user)):
    try:
        thread_id = f"user_{uuid.uuid4().hex}"
        title = data.title or "New Trip Plan"
        chat = create_chat(current_user["id"], thread_id, title)
        return {
            "success": True,
            "chat": {
                "thread_id": chat["thread_id"],
                "title": chat["title"]
            }
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to create chat: {str(e)}"}
        )

@app.get("/api/chats/{thread_id}")
async def get_chat_history(thread_id: str, current_user = Depends(get_current_user)):
    try:
        # Check if chat belongs to the user
        chats = get_user_chats(current_user["id"])
        user_threads = [c["thread_id"] for c in chats]
        
        if thread_id not in user_threads:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this thread."
            )
            
        messages = get_chat_messages(thread_id)
        formatted_msgs = []
        for msg in messages:
            formatted_msgs.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return {"success": True, "messages": formatted_msgs}
    except HTTPException as he:
        raise he
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": f"Failed to load chat history: {str(e)}"}
        )


# =====================================================================
# AI Planner Endpoint
# =====================================================================

@app.post("/api/travel")
async def travel_planner(request_data: TravelRequest, current_user = Depends(get_current_user)):
    try:
        user_message = request_data.message.strip()

        if not user_message:
            return JSONResponse(
                status_code=400,
                content={
                    "success": False,
                    "error": "Message cannot be empty."
                }
            )

        thread_id = request_data.thread_id
        
        # If no thread_id passed or if thread_id is not linked to this user, create a new chat
        chats = get_user_chats(current_user["id"])
        user_threads = [c["thread_id"] for c in chats]
        
        is_new_chat = False
        if not thread_id or thread_id not in user_threads:
            thread_id = f"user_{uuid.uuid4().hex}"
            
            # Auto-generate a title based on destination mentions
            mentions = find_location_mentions(user_message)
            if mentions:
                title = f"Trip to {', '.join([m.title() for m in mentions[:2]])}"
            else:
                title = user_message[:25] + "..." if len(user_message) > 25 else user_message
            
            create_chat(current_user["id"], thread_id, title)
            is_new_chat = True
        else:
            # If it's an existing chat, but was previously titled "New Trip Plan", update its title
            existing_chat = next(c for c in chats if c["thread_id"] == thread_id)
            if existing_chat["title"] == "New Trip Plan":
                mentions = find_location_mentions(user_message)
                if mentions:
                    new_title = f"Trip to {', '.join([m.title() for m in mentions[:2]])}"
                    update_chat_title(thread_id, new_title)

        # Run the Multi-Agent agent
        result = run_travel_agent(
            user_input=user_message,
            thread_id=thread_id
        )
        
        # Save messages to database history
        save_chat_message(thread_id, "user", user_message)
        save_chat_message(thread_id, "assistant", result["answer"])

        return JSONResponse(
            content={
                "success": True,
                "thread_id": result["thread_id"],
                "answer": result["answer"],
                "flight_results": result["flight_results"],
                "hotel_results": result["hotel_results"],
                "ground_transport_results": result["ground_transport_results"],
                "weather_results": result["weather_results"],
                "budget_breakdown": result["budget_breakdown"],
                "itinerary": result["itinerary"],
                "llm_calls": result["llm_calls"],
            }
        )

    except Exception as e:
        print("ERROR:", e)
        traceback.print_exc()

        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": str(e)
            }
        )


# =====================================================================
# Health and Favicon Endpoints
# =====================================================================

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "message": "MoodyTrips AI API is running"
    }


@app.get("/favicon.ico")
async def favicon():
    return JSONResponse(content={})


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )