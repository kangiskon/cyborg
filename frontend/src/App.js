import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowRight,
  Bot,
  Building2,
  CalendarCheck,
  Check,
  Clock3,
  Headphones,
  Inbox,
  LockKeyhole,
  MessageCircle,
  PhoneCall,
  Send,
  Sparkles,
  UserRound,
} from "lucide-react";
import { Toaster, toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const STAFF_TOKEN_STORAGE_KEY = "frontkind_staff_token";

const ICON_SIZE = {
  tiny: 15,
  inputAction: 17,
  action: 18,
  cardlet: 19,
  stat: 20,
  panel: 24,
};

const STAT_TILE_MOTION = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45 },
};

const CHAT_MESSAGE_MOTION = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
};

const SCROLL_INTO_VIEW_OPTIONS = { behavior: "smooth" };
const DEFAULT_SERVICES = ["New client consultation"];
const EMPTY_LEAD = { name: "", phone: "", email: "", interest: "", preferred_contact_time: "" };
const EMPTY_STAFF_LOGIN = { accessCode: "" };
const TEST_ID_SANITIZER = /[^a-z0-9]+/g;

const quickPrompts = [
  "Do you have openings today?",
  "I need a callback from the team.",
  "What services can I book?",
  "Can you explain your hours?",
];

const initialMessage = {
  id: "welcome-message",
  role: "receptionist",
  content:
    "Good morning — I’m your AI receptionist. I can answer questions, collect details for follow-up, and help you book an appointment.",
};

const todayIso = () => new Date().toISOString().slice(0, 10);

const toTestId = (value) => value.toLowerCase().replace(TEST_ID_SANITIZER, "-");

const createChatMessage = (role, content, prefix) => ({
  id: `${prefix}-${Date.now()}`,
  role,
  content,
});

const authHeaders = (token) => ({ Authorization: `Bearer ${token}` });

const buildStats = (dashboard) => [
  {
    icon: CalendarCheck,
    label: "Appointments today",
    value: dashboard?.appointments_today ?? "—",
    detail: "Confirmed through reception",
    testId: "appointments-today-stat",
  },
  {
    icon: PhoneCall,
    label: "Open leads",
    value: dashboard?.open_leads ?? "—",
    detail: "Waiting for staff callback",
    testId: "open-leads-stat",
  },
  {
    icon: MessageCircle,
    label: "Conversations",
    value: dashboard?.total_conversations ?? "—",
    detail: "Persistent chat sessions",
    testId: "conversation-count-stat",
  },
];

function StatTile({ icon: Icon, label, value, detail, testId }) {
  return (
    <motion.div
      data-testid={testId}
      className="stat-tile"
      initial={STAT_TILE_MOTION.initial}
      animate={STAT_TILE_MOTION.animate}
      transition={STAT_TILE_MOTION.transition}
    >
      <div className="stat-icon" data-testid={`${testId}-icon`}>
        <Icon size={ICON_SIZE.stat} />
      </div>
      <p data-testid={`${testId}-label`}>{label}</p>
      <strong data-testid={`${testId}-value`}>{value}</strong>
      <span data-testid={`${testId}-detail`}>{detail}</span>
    </motion.div>
  );
}

function ChatPanel({ messages, setMessages, sessionId, setSessionId }) {
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView(SCROLL_INTO_VIEW_OPTIONS);
  }, [messages]);

  const sendMessage = useCallback(async (text = input) => {
    const clean = text.trim();
    if (!clean || sending) return;
    const visitorMessage = createChatMessage("visitor", clean, "visitor");
    setMessages((current) => [...current, visitorMessage]);
    setInput("");
    setSending(true);
    try {
      const response = await axios.post(`${API}/chat/message`, {
        session_id: sessionId,
        message: clean,
      });
      setSessionId(response.data.session_id);
      setMessages((current) => [
        ...current,
        createChatMessage("receptionist", response.data.message, "receptionist"),
      ]);
    } catch (error) {
      toast.error("The receptionist could not reply just now.");
      setMessages((current) => [
        ...current,
        createChatMessage("receptionist", "I’m having trouble connecting. Please try again in a moment.", "error"),
      ]);
    } finally {
      setSending(false);
    }
  }, [input, sending, sessionId, setMessages, setSessionId]);

  const handleSubmit = (event) => {
    event.preventDefault();
    sendMessage();
  };

  return (
    <section className="chat-panel" data-testid="ai-receptionist-chat-panel">
      <div className="panel-heading">
        <div>
          <span data-testid="chat-panel-kicker">Live reception desk</span>
          <h2 data-testid="chat-panel-title">AI receptionist</h2>
        </div>
        <div className="presence" data-testid="chat-presence-indicator">
          <span /> Available now
        </div>
      </div>

      <div className="message-list" data-testid="chat-message-list">
        <AnimatePresence initial={false}>
          {messages.map((message) => (
            <motion.div
              data-testid={`chat-message-${message.id}`}
              key={message.id}
              className={`message-row ${message.role}`}
              initial={CHAT_MESSAGE_MOTION.initial}
              animate={CHAT_MESSAGE_MOTION.animate}
              exit={CHAT_MESSAGE_MOTION.exit}
            >
              <div className="message-avatar" data-testid={`chat-message-${message.id}-avatar`}>
                {message.role === "visitor" ? <UserRound size={ICON_SIZE.tiny} /> : <Bot size={ICON_SIZE.tiny} />}
              </div>
              <p data-testid={`chat-message-${message.id}-content`}>{message.content}</p>
            </motion.div>
          ))}
        </AnimatePresence>
        {sending && (
          <div className="typing" data-testid="chat-typing-indicator">
            <span /> <span /> <span />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="quick-row" data-testid="chat-quick-prompts">
        {quickPrompts.map((prompt) => (
          <button
            type="button"
            data-testid={`quick-prompt-${toTestId(prompt)}`}
            key={prompt}
            onClick={() => sendMessage(prompt)}
          >
            {prompt}
          </button>
        ))}
      </div>

      <form
        data-testid="chat-input-form"
        className="chat-input-row"
        onSubmit={handleSubmit}
      >
        <Input
          data-testid="chat-message-input"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask a question or request an appointment..."
        />
        <Button data-testid="chat-submit-button" type="submit" disabled={sending}>
          <Send size={ICON_SIZE.inputAction} />
          Send
        </Button>
      </form>
    </section>
  );
}

function BookingPanel({ profile, refreshDashboard }) {
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    service: "New client consultation",
    date: todayIso(),
    time: "",
    notes: "",
  });
  const [slots, setSlots] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const loadSlots = useCallback(async (date) => {
    try {
      const response = await axios.get(`${API}/appointments/slots`, { params: { date } });
      setSlots(response.data.slots);
      const firstAvailable = response.data.slots.find((slot) => slot.available);
      setForm((current) => ({ ...current, time: firstAvailable?.time || "" }));
    } catch (error) {
      toast.error("Could not load appointment slots.");
    }
  }, []);

  useEffect(() => {
    loadSlots(form.date);
  }, [form.date, loadSlots]);

  const updateField = useCallback((field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  }, []);

  const submitBooking = async (event) => {
    event.preventDefault();
    if (!form.time) {
      toast.error("Please choose an available time.");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/appointments`, form);
      toast.success("Appointment confirmed.");
      setForm((current) => ({ ...current, name: "", phone: "", email: "", notes: "" }));
      await loadSlots(form.date);
      refreshDashboard();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not book that time.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="booking-panel" data-testid="appointment-booking-panel">
      <div className="panel-heading compact">
        <div>
          <span data-testid="booking-panel-kicker">Appointment flow</span>
          <h2 data-testid="booking-panel-title">Book a visit</h2>
        </div>
        <CalendarCheck data-testid="booking-panel-icon" size={ICON_SIZE.panel} />
      </div>

      <form className="booking-form" data-testid="appointment-booking-form" onSubmit={submitBooking}>
        <div className="form-pair">
          <Label data-testid="booking-name-label" htmlFor="booking-name">Name</Label>
          <Input data-testid="booking-name-input" id="booking-name" value={form.name} onChange={(event) => updateField("name", event.target.value)} required />
        </div>
        <div className="form-pair">
          <Label data-testid="booking-phone-label" htmlFor="booking-phone">Phone</Label>
          <Input data-testid="booking-phone-input" id="booking-phone" value={form.phone} onChange={(event) => updateField("phone", event.target.value)} required />
        </div>
        <div className="form-pair wide">
          <Label data-testid="booking-email-label" htmlFor="booking-email">Email</Label>
          <Input data-testid="booking-email-input" id="booking-email" type="email" value={form.email} onChange={(event) => updateField("email", event.target.value)} />
        </div>
        <div className="form-pair wide">
          <Label data-testid="booking-service-label" htmlFor="booking-service">Service</Label>
          <select
            data-testid="booking-service-select"
            id="booking-service"
            value={form.service}
            onChange={(event) => updateField("service", event.target.value)}
          >
            {(profile?.services || DEFAULT_SERVICES).map((service) => (
              <option data-testid={`booking-service-option-${toTestId(service)}`} key={service} value={service}>{service}</option>
            ))}
          </select>
        </div>
        <div className="form-pair">
          <Label data-testid="booking-date-label" htmlFor="booking-date">Date</Label>
          <Input data-testid="booking-date-input" id="booking-date" type="date" min={todayIso()} value={form.date} onChange={(event) => updateField("date", event.target.value)} required />
        </div>
        <div className="form-pair">
          <Label data-testid="booking-time-label" htmlFor="booking-time">Time</Label>
          <select data-testid="booking-time-select" id="booking-time" value={form.time} onChange={(event) => updateField("time", event.target.value)} required>
            <option data-testid="booking-time-option-empty" value="">Choose time</option>
            {slots.map((slot) => (
              <option data-testid={`booking-time-option-${slot.time.replace(":", "-")}`} key={slot.time} disabled={!slot.available} value={slot.time}>
                {slot.time} {slot.available ? "" : "— booked"}
              </option>
            ))}
          </select>
        </div>
        <div className="form-pair wide">
          <Label data-testid="booking-notes-label" htmlFor="booking-notes">Notes</Label>
          <Textarea data-testid="booking-notes-input" id="booking-notes" value={form.notes} onChange={(event) => updateField("notes", event.target.value)} placeholder="Anything the team should know?" />
        </div>
        <Button data-testid="booking-submit-button" className="primary-action" type="submit" disabled={submitting}>
          <Check size={ICON_SIZE.action} /> Confirm appointment
        </Button>
      </form>
    </section>
  );
}

function LeadPanel({ refreshDashboard }) {
  const [lead, setLead] = useState(EMPTY_LEAD);
  const [submitting, setSubmitting] = useState(false);

  const updateLead = (field, value) => setLead((current) => ({ ...current, [field]: value }));

  const submitLead = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await axios.post(`${API}/leads`, lead);
      toast.success("Callback request saved.");
      setLead(EMPTY_LEAD);
      refreshDashboard();
    } catch (error) {
      toast.error("Could not save the callback request.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="lead-panel" data-testid="lead-capture-panel">
      <div className="panel-heading compact">
        <div>
          <span data-testid="lead-panel-kicker">Callback queue</span>
          <h2 data-testid="lead-panel-title">Capture lead details</h2>
        </div>
        <PhoneCall data-testid="lead-panel-icon" size={ICON_SIZE.panel} />
      </div>
      <form className="lead-form" data-testid="lead-capture-form" onSubmit={submitLead}>
        <Input data-testid="lead-name-input" placeholder="Full name" value={lead.name} onChange={(event) => updateLead("name", event.target.value)} required />
        <Input data-testid="lead-phone-input" placeholder="Phone number" value={lead.phone} onChange={(event) => updateLead("phone", event.target.value)} required />
        <Input data-testid="lead-email-input" placeholder="Email, optional" type="email" value={lead.email} onChange={(event) => updateLead("email", event.target.value)} />
        <Input data-testid="lead-contact-time-input" placeholder="Preferred callback time" value={lead.preferred_contact_time} onChange={(event) => updateLead("preferred_contact_time", event.target.value)} />
        <Textarea data-testid="lead-interest-input" placeholder="What do they need help with?" value={lead.interest} onChange={(event) => updateLead("interest", event.target.value)} required />
        <Button data-testid="lead-submit-button" className="secondary-action" type="submit" disabled={submitting}>
          <Inbox size={ICON_SIZE.action} /> Save callback request
        </Button>
      </form>
    </section>
  );
}

function StaffLoginPanel({ onLogin }) {
  const [form, setForm] = useState(EMPTY_STAFF_LOGIN);
  const [submitting, setSubmitting] = useState(false);

  const submitLogin = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const response = await axios.post(`${API}/auth/staff-login`, {
        access_code: form.accessCode,
      });
      localStorage.setItem(STAFF_TOKEN_STORAGE_KEY, response.data.token);
      onLogin({ token: response.data.token, staff: response.data.staff });
      setForm(EMPTY_STAFF_LOGIN);
      toast.success("Staff access granted.");
    } catch (error) {
      toast.error(error.response?.data?.detail || "Invalid staff access code.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="staff-login-panel" data-testid="staff-login-panel">
      <div className="panel-heading compact">
        <div>
          <span data-testid="staff-login-kicker">Protected area</span>
          <h2 data-testid="staff-login-title">Staff login</h2>
        </div>
        <LockKeyhole data-testid="staff-login-icon" size={ICON_SIZE.panel} />
      </div>
      <p data-testid="staff-login-description">
        Enter a staff access code to view the receptionist inbox, appointments, and lead handoff details.
      </p>
      <form className="staff-login-form" data-testid="staff-login-form" onSubmit={submitLogin}>
        <Label data-testid="staff-code-label" htmlFor="staff-access-code">Access code</Label>
        <Input
          data-testid="staff-code-input"
          id="staff-access-code"
          value={form.accessCode}
          onChange={(event) => setForm({ accessCode: event.target.value })}
          placeholder="Enter staff access code"
          type="password"
          required
        />
        <Button data-testid="staff-login-submit-button" className="primary-action" type="submit" disabled={submitting}>
          <LockKeyhole size={ICON_SIZE.action} /> Unlock staff inbox
        </Button>
      </form>
    </section>
  );
}

function StaffBadge({ staffAuth, onLogout }) {
  if (!staffAuth?.staff) return null;

  return (
    <div className="staff-badge" data-testid="staff-session-badge">
      <div data-testid="staff-session-details">
        <strong data-testid="staff-session-name">{staffAuth.staff.name}</strong>
        <span data-testid="staff-session-role">{staffAuth.staff.role}</span>
      </div>
      <button data-testid="staff-logout-button" type="button" onClick={onLogout}>Log out</button>
    </div>
  );
}

function InboxPanel({ dashboard, staffAuth, onLogin, onLogout }) {
  if (!staffAuth?.token) {
    return <StaffLoginPanel onLogin={onLogin} />;
  }

  return (
    <section className="inbox-panel" data-testid="operations-inbox-panel">
      <StaffBadge staffAuth={staffAuth} onLogout={onLogout} />
      <div className="panel-heading compact">
        <div>
          <span data-testid="inbox-panel-kicker">Today’s handoff</span>
          <h2 data-testid="inbox-panel-title">Reception inbox</h2>
        </div>
        <Headphones data-testid="inbox-panel-icon" size={ICON_SIZE.panel} />
      </div>
      <div className="handoff-list" data-testid="appointments-handoff-list">
        <h3 data-testid="appointments-handoff-title">Upcoming appointments</h3>
        {(dashboard?.next_appointments || []).length === 0 ? (
          <p data-testid="appointments-empty-state">No appointments booked yet.</p>
        ) : (
          dashboard.next_appointments.map((appointment) => (
            <div data-testid={`appointment-item-${appointment.id}`} className="handoff-item" key={appointment.id}>
              <div>
                <strong data-testid={`appointment-item-${appointment.id}-name`}>{appointment.name}</strong>
                <span data-testid={`appointment-item-${appointment.id}-service`}>{appointment.service}</span>
              </div>
              <time data-testid={`appointment-item-${appointment.id}-time`}>{appointment.date} · {appointment.time}</time>
            </div>
          ))
        )}
      </div>
      <div className="handoff-list" data-testid="leads-handoff-list">
        <h3 data-testid="leads-handoff-title">New callback requests</h3>
        {(dashboard?.recent_leads || []).length === 0 ? (
          <p data-testid="leads-empty-state">No callback requests yet.</p>
        ) : (
          dashboard.recent_leads.map((item) => (
            <div data-testid={`lead-item-${item.id}`} className="handoff-item" key={item.id}>
              <div>
                <strong data-testid={`lead-item-${item.id}-name`}>{item.name}</strong>
                <span data-testid={`lead-item-${item.id}-interest`}>{item.interest}</span>
              </div>
              <time data-testid={`lead-item-${item.id}-phone`}>{item.phone}</time>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function ProfilePanel({ profile, setProfile, staffAuth }) {
  const [editing, setEditing] = useState(null);
  const canEditProfile = staffAuth?.staff?.role === "admin";

  const saveProfileField = useCallback(async (field, value) => {
    const nextProfile = { ...profile, [field]: value };
    setProfile(nextProfile);
    setEditing(null);
    try {
      await axios.patch(`${API}/business-profile`, { [field]: value }, {
        headers: authHeaders(staffAuth.token),
      });
      toast.success("Business profile updated.");
    } catch (error) {
      toast.error("Could not update profile.");
    }
  }, [profile, setProfile, staffAuth]);

  if (!profile) return null;

  return (
    <section className="profile-panel" data-testid="business-profile-panel">
      <div className="panel-heading compact">
        <div>
          <span data-testid="profile-panel-kicker">Reception knowledge</span>
          <h2 data-testid="profile-panel-title">Business profile</h2>
        </div>
        <Building2 data-testid="profile-panel-icon" size={ICON_SIZE.panel} />
      </div>
      <div className="profile-stack" data-testid="profile-field-list">
        <div className="profile-field" data-testid="profile-business-name-field">
          <span data-testid="profile-business-name-label">Business</span>
          {editing === "business_name" ? (
            <Input
              data-testid="profile-business-name-input"
              autoFocus
              defaultValue={profile.business_name}
              onBlur={(event) => saveProfileField("business_name", event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && saveProfileField("business_name", event.currentTarget.value)}
            />
          ) : canEditProfile ? (
            <button data-testid="profile-business-name-button" type="button" onClick={() => setEditing("business_name")}>{profile.business_name}</button>
          ) : (
            <strong data-testid="profile-business-name-readonly">{profile.business_name}</strong>
          )}
        </div>
        <div className="profile-field" data-testid="profile-hours-field">
          <span data-testid="profile-hours-label">Hours</span>
          {editing === "hours" ? (
            <Input
              data-testid="profile-hours-input"
              autoFocus
              defaultValue={profile.hours}
              onBlur={(event) => saveProfileField("hours", event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && saveProfileField("hours", event.currentTarget.value)}
            />
          ) : canEditProfile ? (
            <button data-testid="profile-hours-button" type="button" onClick={() => setEditing("hours")}>{profile.hours}</button>
          ) : (
            <strong data-testid="profile-hours-readonly">{profile.hours}</strong>
          )}
        </div>
        <div className="service-pills" data-testid="profile-service-pill-list">
          {profile.business_types.map((type) => (
            <span data-testid={`profile-business-type-${toTestId(type)}`} key={type}>{type}</span>
          ))}
        </div>
        <div className="faq-mini" data-testid="profile-faq-list">
          {profile.faq.slice(0, 3).map((item, index) => (
            <details data-testid={`profile-faq-item-${index}`} key={item.question}>
              <summary data-testid={`profile-faq-item-${index}-question`}>{item.question}</summary>
              <p data-testid={`profile-faq-item-${index}-answer`}>{item.answer}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

const Home = () => {
  const [profile, setProfile] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [messages, setMessages] = useState([initialMessage]);
  const [sessionId, setSessionId] = useState(null);
  const [staffAuth, setStaffAuth] = useState(null);

  const loadPublicData = useCallback(async () => {
    try {
      const profileResponse = await axios.get(`${API}/business-profile`);
      setProfile(profileResponse.data);
    } catch (error) {
      toast.error("Could not load receptionist workspace.");
    }
  }, []);

  const loadProtectedData = useCallback(async (token) => {
    if (!token) {
      setDashboard(null);
      return;
    }
    try {
      const dashboardResponse = await axios.get(`${API}/dashboard`, {
        headers: authHeaders(token),
      });
      setDashboard(dashboardResponse.data);
    } catch (error) {
      if (error.response?.status === 401 || error.response?.status === 403) {
        localStorage.removeItem(STAFF_TOKEN_STORAGE_KEY);
        setStaffAuth(null);
        setDashboard(null);
        toast.error("Staff session expired. Please log in again.");
      } else {
        toast.error("Could not load staff inbox.");
      }
    }
  }, []);

  useEffect(() => {
    loadPublicData();
  }, [loadPublicData]);

  useEffect(() => {
    const savedToken = localStorage.getItem(STAFF_TOKEN_STORAGE_KEY);
    if (!savedToken) return;

    const restoreStaffSession = async () => {
      try {
        const response = await axios.get(`${API}/auth/me`, {
          headers: authHeaders(savedToken),
        });
        setStaffAuth({ token: savedToken, staff: response.data });
        await loadProtectedData(savedToken);
      } catch (error) {
        localStorage.removeItem(STAFF_TOKEN_STORAGE_KEY);
      }
    };

    restoreStaffSession();
  }, [loadProtectedData]);

  const handleStaffLogin = useCallback((nextStaffAuth) => {
    setStaffAuth(nextStaffAuth);
    loadProtectedData(nextStaffAuth.token);
  }, [loadProtectedData]);

  const handleStaffLogout = useCallback(() => {
    localStorage.removeItem(STAFF_TOKEN_STORAGE_KEY);
    setStaffAuth(null);
    setDashboard(null);
    toast.success("Staff logged out.");
  }, []);

  const refreshDashboard = useCallback(() => {
    loadProtectedData(staffAuth?.token);
  }, [loadProtectedData, staffAuth?.token]);

  const stats = useMemo(() => buildStats(dashboard), [dashboard]);

  return (
    <div className="reception-app" data-testid="ai-receptionist-app">
      <Toaster richColors position="top-right" />
      <nav className="top-nav" data-testid="top-navigation">
        <a data-testid="brand-home-link" href="/" className="brand-mark">
          <span data-testid="brand-icon"><Sparkles size={ICON_SIZE.action} /></span>
          <strong data-testid="brand-name">Frontkind</strong>
        </a>
        <div className="nav-actions" data-testid="navigation-actions">
          <a data-testid="nav-chat-link" href="#chat">Reception</a>
          <a data-testid="nav-booking-link" href="#booking">Booking</a>
          <a data-testid="nav-inbox-link" href="#inbox">Inbox</a>
        </div>
      </nav>

      <main data-testid="main-workspace">
        <section className="hero-band" data-testid="hero-section">
          <div className="hero-copy" data-testid="hero-copy">
            <span className="eyebrow" data-testid="hero-eyebrow"><Clock3 size={ICON_SIZE.tiny} /> Always-on front desk</span>
            <h1 data-testid="hero-title">A calm AI receptionist for every small business front door.</h1>
            <p data-testid="hero-subtitle">
              Answer questions, collect warm leads, and confirm appointments from one focused reception workspace.
            </p>
            <div className="hero-actions" data-testid="hero-actions">
              <a data-testid="hero-start-chat-link" href="#chat" className="hero-primary">Start greeting visitors <ArrowRight size={ICON_SIZE.action} /></a>
              <a data-testid="hero-booking-link" href="#booking" className="hero-secondary">Open booking desk</a>
            </div>
          </div>
          <div className="hero-visual" data-testid="hero-visual">
            <img
              data-testid="hero-background-image"
              src="https://images.unsplash.com/photo-1773924093206-9a433a14bb44?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85"
              alt="Warm reception interior"
            />
            <div className="hero-cardlet" data-testid="hero-live-cardlet">
              <Bot size={ICON_SIZE.cardlet} />
              <span data-testid="hero-live-cardlet-text">Greeting visitor · collecting details</span>
            </div>
          </div>
        </section>

        <section className="stats-grid" data-testid="dashboard-stats-grid">
          {stats.map((stat) => <StatTile key={stat.testId} {...stat} />)}
        </section>

        <section className="workspace-grid" data-testid="control-room-grid">
          <div id="chat" className="workspace-main" data-testid="workspace-main-column">
            <ChatPanel messages={messages} setMessages={setMessages} sessionId={sessionId} setSessionId={setSessionId} />
          </div>
          <aside className="workspace-side" data-testid="workspace-side-column">
            <ProfilePanel profile={profile} setProfile={setProfile} staffAuth={staffAuth} />
          </aside>
        </section>

        <section id="booking" className="workflow-grid" data-testid="booking-and-lead-grid">
          <BookingPanel profile={profile} refreshDashboard={refreshDashboard} />
          <LeadPanel refreshDashboard={refreshDashboard} />
        </section>

        <section id="inbox" className="inbox-grid" data-testid="inbox-section">
          <InboxPanel dashboard={dashboard} staffAuth={staffAuth} onLogin={handleStaffLogin} onLogout={handleStaffLogout} />
        </section>
      </main>
    </div>
  );
};

function App() {
  return (
    <div className="App" data-testid="app-root">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
