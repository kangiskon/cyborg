export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const HTTP_UNAUTHORIZED = 401;
export const HTTP_FORBIDDEN = 403;

export const HTTP_STATUS = {
  unauthorized: HTTP_UNAUTHORIZED,
  forbidden: HTTP_FORBIDDEN,
};

const ICON_INLINE_SMALL = 15;
const ICON_INPUT_BUTTON = 17;
const ICON_ACTION = 18;
const ICON_HERO_STATUS = 19;
const ICON_STAT = 20;
const ICON_PANEL = 24;

export const ICON_SIZE = {
  tiny: ICON_INLINE_SMALL,
  inputAction: ICON_INPUT_BUTTON,
  action: ICON_ACTION,
  cardlet: ICON_HERO_STATUS,
  stat: ICON_STAT,
  panel: ICON_PANEL,
};

export const DEFAULT_SERVICES = ["New client consultation"];
export const EMPTY_LEAD = { name: "", phone: "", email: "", interest: "", preferred_contact_time: "" };
export const EMPTY_STAFF_LOGIN = { accessCode: "" };
export const DEFAULT_NOTIFICATION_FILTERS = { type: "all", status: "all" };
export const DEFAULT_AUDIT_FILTERS = { action: "all", actorRole: "all" };
export const NOTIFICATION_TYPES = ["all", "appointment", "lead", "lead_suggestion", "staff_security"];
export const NOTIFICATION_STATUSES = ["all", "unread", "read"];
export const AUDIT_ACTIONS = ["all", "login", "logout", "view", "profile_update", "notification_read", "lead_approved", "export"];
export const AUDIT_ROLES = ["all", "admin", "staff", "viewer", "system"];

export const STAT_TILE_MOTION = {
  initial: { opacity: 0, y: 14 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.45 },
};

export const CHAT_MESSAGE_MOTION = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0 },
};

export const SCROLL_INTO_VIEW_OPTIONS = { behavior: "smooth" };

export const quickPrompts = [
  "Do you have openings today?",
  "I need a callback from the team.",
  "What services can I book?",
  "Can you explain your hours?",
];

export const initialMessage = {
  id: "welcome-message",
  role: "receptionist",
  content:
    "Good morning — I’m your AI receptionist. I can answer questions, collect details for follow-up, and help you book an appointment.",
};