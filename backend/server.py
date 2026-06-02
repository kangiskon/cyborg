from fastapi import Depends, FastAPI, APIRouter, HTTPException, Header
from dotenv import load_dotenv
from starlette.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import re
from pathlib import Path
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from typing import Any, Dict, List, Optional
import uuid
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
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

AVAILABLE_SLOTS = ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "13:00", "13:30", "14:00", "14:30", "15:00", "15:30", "16:00"]
JWT_ALGORITHM = "HS256"
STAFF_TOKEN_EXPIRE_HOURS = 8
ROLE_RANK = {"viewer": 1, "staff": 2, "admin": 3}
NOTIFICATION_TARGET_ROLES = ["admin", "staff"]
CONTACT_INTENT_KEYWORDS = ["callback", "call me", "appointment", "book", "schedule", "consultation", "viewing", "follow up", "follow-up"]
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{6,}\d)")
NAME_PATTERNS = [
    re.compile(r"(?:my name is|i am|i'm|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.IGNORECASE),
    re.compile(r"name[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})", re.IGNORECASE),
]


def staff_directory() -> Dict[str, Dict[str, str]]:
    return {
        os.environ["STAFF_ADMIN_ACCESS_CODE"]: {
            "id": "admin-frontkind",
            "email": "admin@frontkind.app",
            "name": "Frontkind Admin",
            "role": "admin",
        },
        os.environ["STAFF_STAFF_ACCESS_CODE"]: {
            "id": "staff-frontkind",
            "email": "staff@frontkind.app",
            "name": "Reception Staff",
            "role": "staff",
        },
        os.environ["STAFF_VIEWER_ACCESS_CODE"]: {
            "id": "viewer-frontkind",
            "email": "viewer@frontkind.app",
            "name": "Inbox Viewer",
            "role": "viewer",
        },
    }


def validate_iso_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("Date must use YYYY-MM-DD format.") from exc
    if parsed < datetime.now(timezone.utc).date():
        raise ValueError("Date cannot be in the past.")
    return value


def validate_phone(value: str) -> str:
    digits = [char for char in value if char.isdigit()]
    if len(digits) < 7:
        raise ValueError("Phone number must include at least 7 digits.")
    return value.strip()


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


class BusinessProfilePartialUpdate(BaseModel):
    business_name: Optional[str] = None
    business_types: Optional[List[str]] = None
    voice: Optional[str] = None
    hours: Optional[str] = None
    location: Optional[str] = None
    services: Optional[List[str]] = None
    faq: Optional[List[Dict[str, str]]] = None


class LeadCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=7)
    interest: str = Field(..., min_length=3)
    preferred_contact_time: Optional[str] = None
    source: str = "receptionist"

    @field_validator("phone")
    @classmethod
    def phone_has_enough_digits(cls, value: str) -> str:
        return validate_phone(value)


class Lead(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[EmailStr] = None
    phone: str
    interest: str
    preferred_contact_time: Optional[str] = None
    source: str = "receptionist"
    status: str = "new"
    session_id: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)


class AppointmentCreate(BaseModel):
    name: str = Field(..., min_length=2)
    email: Optional[EmailStr] = None
    phone: str = Field(..., min_length=7)
    service: str
    date: str
    time: str
    notes: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def phone_has_enough_digits(cls, value: str) -> str:
        return validate_phone(value)

    @field_validator("date")
    @classmethod
    def date_is_valid_iso(cls, value: str) -> str:
        return validate_iso_date(value)

    @field_validator("time")
    @classmethod
    def time_is_bookable_slot(cls, value: str) -> str:
        if value not in AVAILABLE_SLOTS:
            raise ValueError("Time must be one of the available appointment slots.")
        return value


class Appointment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: Optional[EmailStr] = None
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


class StaffLoginRequest(BaseModel):
    access_code: str = Field(..., min_length=6)


class StaffUser(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: str


class StaffLoginResponse(BaseModel):
    token: str
    staff: StaffUser


class Notification(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str
    title: str
    message: str
    target_roles: List[str] = Field(default_factory=lambda: NOTIFICATION_TARGET_ROLES.copy())
    related_id: Optional[str] = None
    read_by: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)


class NotificationList(BaseModel):
    notifications: List[Notification]
    unread_count: int


class AuditLog(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    actor_id: str
    actor_name: str
    actor_role: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    detail: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)


class AuditLogList(BaseModel):
    logs: List[AuditLog]


class LeadApproveResponse(BaseModel):
    lead: Lead

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "AI receptionist API is ready"}


def create_staff_token(staff: Dict[str, str]) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=STAFF_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": staff["id"],
        "email": staff["email"],
        "name": staff["name"],
        "role": staff["role"],
        "exp": expires_at,
    }
    return jwt.encode(payload, os.environ["STAFF_AUTH_SECRET"], algorithm=JWT_ALGORITHM)


async def write_audit_log(staff: StaffUser, action: str, resource: str, resource_id: Optional[str] = None, detail: Optional[str] = None) -> AuditLog:
    log = AuditLog(
        actor_id=staff.id,
        actor_name=staff.name,
        actor_role=staff.role,
        action=action,
        resource=resource,
        resource_id=resource_id,
        detail=detail,
    )
    await db.audit_logs.insert_one(log.model_dump())
    return log


async def create_system_audit(action: str, resource: str, resource_id: Optional[str] = None, detail: Optional[str] = None) -> AuditLog:
    log = AuditLog(
        actor_id="system",
        actor_name="System",
        actor_role="system",
        action=action,
        resource=resource,
        resource_id=resource_id,
        detail=detail,
    )
    await db.audit_logs.insert_one(log.model_dump())
    return log


async def create_notification(notification_type: str, title: str, message: str, related_id: Optional[str] = None) -> Notification:
    notification = Notification(
        type=notification_type,
        title=title,
        message=message,
        related_id=related_id,
    )
    await db.notifications.insert_one(notification.model_dump())
    return notification


async def get_current_staff(authorization: Optional[str] = Header(default=None)) -> StaffUser:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Staff login required.")
    token = authorization.replace("Bearer ", "", 1).strip()
    try:
        payload = jwt.decode(token, os.environ["STAFF_AUTH_SECRET"], algorithms=[JWT_ALGORITHM])
        staff = StaffUser(
            id=payload["sub"],
            email=payload["email"],
            name=payload["name"],
            role=payload["role"],
        )
    except (JWTError, KeyError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired staff login.") from exc
    return staff


def require_role(min_role: str):
    async def checker(staff: StaffUser = Depends(get_current_staff)) -> StaffUser:
        if ROLE_RANK.get(staff.role, 0) < ROLE_RANK[min_role]:
            raise HTTPException(status_code=403, detail="Your staff role cannot access this area.")
        return staff

    return checker


@api_router.post("/auth/staff-login", response_model=StaffLoginResponse)
async def staff_login(input_data: StaffLoginRequest):
    staff = staff_directory().get(input_data.access_code.strip())
    if not staff:
        raise HTTPException(status_code=401, detail="Invalid staff access code.")
    staff_user = StaffUser(**staff)
    await write_audit_log(staff_user, "login", "staff_session", staff_user.id, "Staff access code login")
    return StaffLoginResponse(token=create_staff_token(staff), staff=staff_user)


@api_router.post("/auth/logout")
async def staff_logout(staff: StaffUser = Depends(get_current_staff)):
    await write_audit_log(staff, "logout", "staff_session", staff.id, "Staff logged out")
    return {"status": "ok"}


@api_router.get("/auth/me", response_model=StaffUser)
async def staff_me(staff: StaffUser = Depends(get_current_staff)):
    return staff


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


def extract_contact_details(text: str) -> Dict[str, Optional[str]]:
    email_match = EMAIL_PATTERN.search(text)
    phone_match = PHONE_PATTERN.search(text)
    name = None
    for pattern in NAME_PATTERNS:
        match = pattern.search(text)
        if match:
            name = match.group(1).strip()
            break
    return {
        "name": name,
        "email": email_match.group(0) if email_match else None,
        "phone": phone_match.group(0).strip() if phone_match else None,
    }


def has_contact_intent(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in CONTACT_INTENT_KEYWORDS)


async def maybe_create_lead_suggestion(session_id: str, visitor_text: str) -> Optional[Lead]:
    details = extract_contact_details(visitor_text)
    has_contact = bool(details.get("phone") or details.get("email"))
    if not (has_contact and has_contact_intent(visitor_text)):
        return None
    duplicate = await db.leads.find_one(
        {
            "session_id": session_id,
            "source": "chat_extraction",
            "status": {"$in": ["suggested", "new"]},
        },
        {"_id": 0},
    )
    if duplicate:
        return Lead(**duplicate)
    lead = Lead(
        name=details.get("name") or "Chat visitor",
        email=details.get("email"),
        phone=details.get("phone") or "0000000",
        interest=visitor_text[:240],
        preferred_contact_time=None,
        source="chat_extraction",
        status="suggested",
        session_id=session_id,
    )
    await db.leads.insert_one(lead.model_dump())
    await create_notification(
        "lead_suggestion",
        "Lead suggested from chat",
        f"{lead.name} may need follow-up from the receptionist chat.",
        lead.id,
    )
    await create_system_audit("lead_suggested", "lead", lead.id, "Automatic chat-to-lead extraction")
    return lead


async def generate_ai_reply(session_id: str, user_text: str) -> str:
    api_key = os.environ.get("EMERGENT_LLM_KEY")
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
async def update_business_profile(input_data: BusinessProfileUpdate, staff: StaffUser = Depends(require_role("admin"))):
    profile = BusinessProfile(**input_data.model_dump(), updated_at=utc_now_iso())
    await db.business_profiles.update_one(
        {"id": profile.id},
        {"$set": profile.model_dump()},
        upsert=True,
    )
    await write_audit_log(staff, "profile_update", "business_profile", profile.id, "Full profile update")
    return profile


@api_router.patch("/business-profile", response_model=BusinessProfile)
async def patch_business_profile(input_data: BusinessProfilePartialUpdate, staff: StaffUser = Depends(require_role("admin"))):
    current = await get_profile_doc()
    updates = input_data.model_dump(exclude_unset=True)
    if not updates:
        return BusinessProfile(**current)
    next_profile = {**current, **updates, "updated_at": utc_now_iso()}
    profile = BusinessProfile(**next_profile)
    await db.business_profiles.update_one(
        {"id": profile.id},
        {"$set": profile.model_dump()},
        upsert=True,
    )
    await write_audit_log(staff, "profile_update", "business_profile", profile.id, f"Updated fields: {', '.join(updates.keys())}")
    return profile


@api_router.get("/dashboard", response_model=DashboardSummary)
async def get_dashboard(staff: StaffUser = Depends(require_role("viewer"))):
    await write_audit_log(staff, "view", "dashboard", detail="Viewed receptionist dashboard")
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
    try:
        validate_iso_date(date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    booked = await db.appointments.find({"date": date}, {"_id": 0, "time": 1}).to_list(100)
    booked_times = {item["time"] for item in booked}
    return {"date": date, "slots": [{"time": slot, "available": slot not in booked_times} for slot in AVAILABLE_SLOTS]}


@api_router.post("/appointments", response_model=Appointment)
async def create_appointment(input_data: AppointmentCreate):
    conflict = await db.appointments.find_one({"date": input_data.date, "time": input_data.time}, {"_id": 0})
    if conflict:
        raise HTTPException(status_code=409, detail="That appointment time is already booked.")
    appointment = Appointment(**input_data.model_dump())
    await db.appointments.insert_one(appointment.model_dump())
    await create_notification(
        "appointment",
        "New appointment booked",
        f"{appointment.name} booked {appointment.service} for {appointment.date} at {appointment.time}.",
        appointment.id,
    )
    await create_system_audit("appointment_created", "appointment", appointment.id, f"{appointment.name} booked {appointment.service}")
    return appointment


@api_router.get("/appointments", response_model=List[Appointment])
async def list_appointments(staff: StaffUser = Depends(require_role("viewer"))):
    await write_audit_log(staff, "view", "appointments", detail="Viewed appointment list")
    appointments = await db.appointments.find({}, {"_id": 0}).sort([("date", 1), ("time", 1)]).to_list(200)
    return [Appointment(**item) for item in appointments]


@api_router.post("/leads", response_model=Lead)
async def create_lead(input_data: LeadCreate):
    lead = Lead(**input_data.model_dump())
    await db.leads.insert_one(lead.model_dump())
    await create_notification(
        "lead",
        "New callback request",
        f"{lead.name} requested follow-up: {lead.interest}",
        lead.id,
    )
    await create_system_audit("lead_created", "lead", lead.id, f"Lead created from {lead.source}")
    return lead


@api_router.get("/leads", response_model=List[Lead])
async def list_leads(staff: StaffUser = Depends(require_role("staff"))):
    await write_audit_log(staff, "view", "leads", detail="Viewed lead list")
    leads = await db.leads.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    return [Lead(**item) for item in leads]


@api_router.post("/leads/{lead_id}/approve", response_model=LeadApproveResponse)
async def approve_suggested_lead(lead_id: str, staff: StaffUser = Depends(require_role("staff"))):
    lead_doc = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    if not lead_doc:
        raise HTTPException(status_code=404, detail="Lead not found.")
    if lead_doc.get("status") != "suggested":
        lead = Lead(**lead_doc)
        return LeadApproveResponse(lead=lead)
    await db.leads.update_one({"id": lead_id}, {"$set": {"status": "new"}})
    updated = await db.leads.find_one({"id": lead_id}, {"_id": 0})
    await create_notification(
        "lead",
        "Suggested lead approved",
        f"{updated['name']} was approved for staff follow-up.",
        lead_id,
    )
    await write_audit_log(staff, "lead_approved", "lead", lead_id, "Approved chat-to-lead suggestion")
    return LeadApproveResponse(lead=Lead(**updated))


@api_router.get("/notifications", response_model=NotificationList)
async def list_notifications(staff: StaffUser = Depends(require_role("viewer"))):
    query = {"target_roles": {"$in": [staff.role]}}
    notifications_raw = await db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(50).to_list(50)
    notifications = [Notification(**item) for item in notifications_raw]
    unread_count = sum(1 for item in notifications if staff.id not in item.read_by)
    await write_audit_log(staff, "view", "notifications", detail="Viewed notification center")
    return NotificationList(notifications=notifications, unread_count=unread_count)


@api_router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, staff: StaffUser = Depends(require_role("viewer"))):
    await db.notifications.update_one(
        {"id": notification_id, "target_roles": {"$in": [staff.role]}},
        {"$addToSet": {"read_by": staff.id}},
    )
    await write_audit_log(staff, "notification_read", "notification", notification_id, "Marked notification as read")
    return {"status": "ok"}


@api_router.get("/audit-logs", response_model=AuditLogList)
async def list_audit_logs(staff: StaffUser = Depends(require_role("admin"))):
    logs_raw = await db.audit_logs.find({}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    await write_audit_log(staff, "view", "audit_logs", detail="Viewed staff audit logs")
    return AuditLogList(logs=[AuditLog(**item) for item in logs_raw])


@api_router.get("/chat/sessions", response_model=List[ChatSession])
async def list_chat_sessions(staff: StaffUser = Depends(require_role("viewer"))):
    await write_audit_log(staff, "view", "chat_sessions", detail="Viewed chat sessions")
    sessions = await db.chat_sessions.find({}, {"_id": 0}).sort("updated_at", -1).to_list(100)
    return [ChatSession(**item) for item in sessions]


@api_router.get("/chat/messages/{session_id}", response_model=List[ChatMessage])
async def get_chat_messages(session_id: str, staff: StaffUser = Depends(require_role("viewer"))):
    await write_audit_log(staff, "view", "chat_messages", session_id, "Viewed chat messages")
    messages = await db.chat_messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(300)
    return [ChatMessage(**item) for item in messages]


@api_router.post("/chat/message", response_model=ChatResponse)
async def chat_message(input_data: ChatMessageCreate):
    session_id = await ensure_session(input_data.session_id, input_data.message)
    await store_message(session_id, "visitor", input_data.message)
    await maybe_create_lead_suggestion(session_id, input_data.message)
    reply = await generate_ai_reply(session_id, input_data.message)
    await store_message(session_id, "receptionist", reply)
    return ChatResponse(session_id=session_id, message=reply, mode="live" if os.environ.get("EMERGENT_LLM_KEY") else "mocked")


@api_router.post("/chat/stream")
async def chat_stream(input_data: ChatMessageCreate):
    session_id = await ensure_session(input_data.session_id, input_data.message)
    await store_message(session_id, "visitor", input_data.message)
    await maybe_create_lead_suggestion(session_id, input_data.message)
    api_key = os.environ.get("EMERGENT_LLM_KEY")
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