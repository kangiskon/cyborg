from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, StreamDone, TextDelta, UserMessage


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


DEFAULT_PROFILE = {
    "id": "default-profile",
    "business_name": "Harbor House Reception",
    "business_types": ["Clinic", "Salon & Spa", "Real Estate", "General Business"],
    "voice": "warm, concise, reassuring, and highly organized",
    "hours": "Monday to Friday, 9:00 AM – 5:00 PM",
    "location": "Downtown service office",
    "services": [
        "New client consultations",
        "Follow-up appointments",
        "Property viewings",
        "Wellness and beauty services",
        "General customer support",
    ],
    "faq": [
        {"question": "Do you accept same-day appointments?", "answer": "Same-day appointments may be available depending on the schedule. The receptionist can check open slots and collect callback details."},
        {"question": "Can I request a callback?", "answer": "Yes. Share your name, phone number, preferred time, and what you need help with."},
        {"question": "What should I bring to an appointment?", "answer": "Bring any relevant documents, identification, and notes about your request so the team can prepare."},
        {"question": "Can I reschedule?", "answer": "Yes. Contact the office with your current appointment details and preferred new times."},
    ],
}


class BusinessProfile(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = "default-profile"
    business_name: str
    business_types: List[str]
    voice: str
    hours: str
    location: str
    services: List[str]
    faq: List[Dict[str, str]]
    updated_at: str = Field(default_factory=utc_now_iso)


class BusinessProfileUpdate(BaseModel):
    business_name: str
    business_types: List[str]
    voice: str
    hours: str
    location: str
    services: List[str]
    faq: List[Dict[str, str]]


class LeadCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: str
    interest: str
    preferred_contact_time: Optional[str] = None
    source: str = "receptionist"


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[str] = None
    phone: str
    interest: str
    preferred_contact_time: Optional[str] = None
    source: str = "receptionist"
    status: str = "new"
    created_at: str = Field(default_factory=utc_now_iso)


class AppointmentCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: str
    service: str
    date: str
    time: str
    notes: Optional[str] = None


class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[str] = None
    phone: str
    service: str
    date: str
    time: str
    notes: Optional[str] = None
    status: str = "confirmed"
    created_at: str = Field(default_factory=utc_now_iso)


class ChatMessageCreate(BaseModel):
    session_id: Optional[str] = None
    message: str


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str
    role: str
    content: str
    created_at: str = Field(default_factory=utc_now_iso)


class ChatSession(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Reception conversation"
    created_at: str = Field(default_factory=utc_now_iso)
    updated_at: str = Field(default_factory=utc_now_iso)


class ChatResponse(BaseModel):
    session_id: str
    message: str
    mode: str = "live"


class DashboardSummary(BaseModel):
    appointments_today: int
    open_leads: int
    total_conversations: int
    next_appointments: List[Appointment]
    recent_leads: List[Lead]

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "AI receptionist API is ready"}


async def get_profile_doc() -> Dict[str, Any]:
    profile = await db.business_profiles.find_one({"id": "default-profile"}, {"_id": 0})
    if profile:
        return profile
    default_profile = {**DEFAULT_PROFILE, "updated_at": utc_now_iso()}
    await db.business_profiles.insert_one(default_profile.copy())
    return default_profile


def system_prompt(profile: Dict[str, Any]) -> str:
    faq_text = "\n".join([f"Q: {item.get('question')}\nA: {item.get('answer')}" for item in profile.get("faq", [])])
    services = ", ".join(profile.get("services", []))
    business_types = ", ".join(profile.get("business_types", []))
    return f"""
You are the AI receptionist for {profile.get('business_name')}.
Business categories: {business_types}.
Tone: {profile.get('voice')}.
Hours: {profile.get('hours')}. Location: {profile.get('location')}.
Services: {services}.

Your job:
1. Answer business FAQ questions accurately using the FAQ and business profile.
2. Collect lead details naturally when someone needs follow-up: name, phone, email if available, need, and preferred callback time.
3. Help visitors choose appointment details, then direct them to the booking panel if a time is needed.
4. Never claim a booking is complete unless the booking form confirms it.
5. Keep replies short, warm, professional, and useful.

FAQ knowledge:
{faq_text}
""".strip()


async def store_message(session_id: str, role: str, content: str) -> ChatMessage:
    message = ChatMessage(session_id=session_id, role=role, content=content)
    await db.chat_messages.insert_one(message.model_dump())
    await db.chat_sessions.update_one(
        {"id": session_id},
        {"$set": {"updated_at": utc_now_iso()}},
        upsert=False,
    )
    return message


async def ensure_session(session_id: Optional[str], first_message: str = "") -> str:
    if session_id:
        existing = await db.chat_sessions.find_one({"id": session_id}, {"_id": 0})
        if existing:
            return session_id
    session = ChatSession(title=(first_message[:42] or "Reception conversation"))
    await db.chat_sessions.insert_one(session.model_dump())
    return session.id


async def generate_ai_reply(session_id: str, user_text: str) -> str:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return "I can help with FAQs, callback details, and booking requests. Please share your name, phone number, and what you need help with."

    profile = await get_profile_doc()
    history = await db.chat_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("created_at", -1).limit(8).to_list(8)
    history.reverse()
    history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history])
    chat = LlmChat(
        api_key=api_key,
        session_id=session_id,
        system_message=system_prompt(profile),
    ).with_model("openai", "gpt-5.2")
    prompt = f"Recent conversation:\n{history_text}\n\nVisitor: {user_text}"
    chunks: List[str] = []
    try:
        async for event in chat.stream_message(UserMessage(text=prompt)):
            if isinstance(event, TextDelta):
                chunks.append(event.content)
            elif isinstance(event, StreamDone):
                break
        return "".join(chunks).strip()
    except Exception as error:
        logger.warning("AI reply generation failed: %s", str(error))
        return "I’m sorry — the live AI service is unavailable right now. I can still collect your details for the team: please share your name, phone number, what you need help with, and your preferred appointment or callback time."


@api_router.get("/business-profile", response_model=BusinessProfile)
async def get_business_profile():
    profile = await get_profile_doc()
    return BusinessProfile(**profile)


@api_router.put("/business-profile", response_model=BusinessProfile)
async def update_business_profile(input_data: BusinessProfileUpdate):
    profile = BusinessProfile(**input_data.model_dump(), updated_at=utc_now_iso())
    await db.business_profiles.update_one(
        {"id": profile.id},
        {"$set": profile.model_dump()},
        upsert=True,
    )
    return profile


@api_router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard():
    today = datetime.now(timezone.utc).date().isoformat()
    appointments_today = await db.appointments.count_documents({"date": today})
    open_leads = await db.leads.count_documents({"status": "new"})
    total_conversations = await db.chat_sessions.count_documents({})
    next_appointments_raw = await db.appointments.find({}, {"_id": 0}).sort([("date", 1), ("time", 1)]).limit(5).to_list(5)
    recent_leads_raw = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    return DashboardSummary(
        appointments_today=appointments_today,
        open_leads=open_leads,
        total_conversations=total_conversations,
        next_appointments=[Appointment(**item) for item in next_appointments_raw],
        recent_leads=[Lead(**item) for item in recent_leads_raw],
    )


@api_router.get("/appointments/slots")
async def get_available_slots(date: str):
    base_slots = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
    booked = await db.appointments.find({"date": date}, {"_id": 0, "time": 1}).to_list(100)
    booked_times = {item["time"] for item in booked}
    return {"date": date, "slots": [{"time": slot, "available": slot not in booked_times} for slot in base_slots]}


@api_router.post("/appointments", response_model=Appointment)
async def create_appointment(input_data: AppointmentCreate):
    conflict = await db.appointments.find_one({"date": input_data.date, "time": input_data.time}, {"_id": 0})
    if conflict:
        raise HTTPException(status_code=409, detail="That appointment time is already booked.")
    appointment = Appointment(**input_data.model_dump())
    await db.appointments.insert_one(appointment.model_dump())
    return appointment


@api_router.get("/appointments", response_model=List[Appointment])
async def list_appointments():
    appointments = await db.appointments.find({}, {"_id": 0}).sort([("date", 1), ("time", 1)]).to_list(200)
    return [Appointment(**item) for item in appointments]


@api_router.post("/leads", response_model=Lead)
async def create_lead(input_data: LeadCreate):
    lead = Lead(**input_data.model_dump())
    await db.leads.insert_one(lead.model_dump())
    return lead


@api_router.get("/leads", response_model=List[Lead])
async def list_leads():
    leads = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [Lead(**item) for item in leads]


@api_router.get("/chat/sessions", response_model=List[ChatSession])
async def list_chat_sessions():
    sessions = await db.chat_sessions.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return [ChatSession(**item) for item in sessions]


@api_router.get("/chat/messages/{session_id}", response_model=List[ChatMessage])
async def get_chat_messages(session_id: str):
    messages = await db.chat_messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(300)
    return [ChatMessage(**item) for item in messages]


@api_router.post("/chat/message", response_model=ChatResponse)
async def chat_message(input_data: ChatMessageCreate):
    session_id = await ensure_session(input_data.session_id, input_data.message)
    await store_message(session_id, "visitor", input_data.message)
    reply = await generate_ai_reply(session_id, input_data.message)
    await store_message(session_id, "receptionist", reply)
    return ChatResponse(session_id=session_id, message=reply, mode="live" if os.environ.get("OPENAI_API_KEY") else "mocked")


@api_router.post("/chat/stream")
async def chat_stream(input_data: ChatMessageCreate):
    session_id = await ensure_session(input_data.session_id, input_data.message)
    await store_message(session_id, "visitor", input_data.message)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        async def mock_generator():
            text = "I can help with FAQs, callbacks, and appointments. Could you share your name, phone number, and what you need help with?"
            yield f"event: session\ndata: {session_id}\n\n"
            yield f"data: {text}\n\n"
            yield "event: done\ndata: complete\n\n"
            await store_message(session_id, "receptionist", text)
        return StreamingResponse(mock_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    profile = await get_profile_doc()

    async def event_generator():
        chunks: List[str] = []
        yield f"event: session\ndata: {session_id}\n\n"
        history = await db.chat_messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", -1).limit(8).to_list(8)
        history.reverse()
        history_text = "\n".join([f"{item['role']}: {item['content']}" for item in history])
        chat = LlmChat(
            api_key=api_key,
            session_id=session_id,
            system_message=system_prompt(profile),
        ).with_model("openai", "gpt-5.2")
        prompt = f"Recent conversation:\n{history_text}\n\nVisitor: {input_data.message}"
        try:
            async for event in chat.stream_message(UserMessage(text=prompt)):
                if isinstance(event, TextDelta):
                    chunks.append(event.content)
                    safe_content = event.content.replace("\n", " ")
                    yield f"data: {safe_content}\n\n"
                elif isinstance(event, StreamDone):
                    break
        except Exception as error:
            logger.warning("AI stream failed: %s", str(error))
            fallback = "I’m sorry — the live AI service is unavailable right now. I can still collect your details for the team: please share your name, phone number, what you need help with, and your preferred appointment or callback time."
            chunks.append(fallback)
            yield f"data: {fallback}\n\n"
        full_reply = "".join(chunks).strip()
        await store_message(session_id, "receptionist", full_reply)
        yield "event: done\ndata: complete\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()