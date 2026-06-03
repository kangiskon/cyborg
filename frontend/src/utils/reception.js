import { API, DEFAULT_AUDIT_FILTERS, DEFAULT_NOTIFICATION_FILTERS } from "@/constants/reception";
import { CalendarCheck, MessageCircle, PhoneCall } from "lucide-react";

const TEST_ID_SANITIZER = /[^a-z0-9]+/g;

export const todayIso = () => new Date().toISOString().slice(0, 10);

export const toTestId = (value) => value.toLowerCase().replace(TEST_ID_SANITIZER, "-");

export const createChatMessage = (role, content, prefix) => ({
  id: `${prefix}-${Date.now()}`,
  role,
  content,
});

export const authHeaders = (token) => ({ Authorization: `Bearer ${token}` });

export const clearStaffState = ({ setStaffAuth, setDashboard, setNotifications, setUnreadCount, setAuditLogs }) => {
  setStaffAuth(null);
  setDashboard(null);
  setNotifications([]);
  setUnreadCount(0);
  setAuditLogs([]);
};

export const buildStats = (dashboard) => [
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

export const buildNotificationParams = (filters = DEFAULT_NOTIFICATION_FILTERS) => ({
  notification_type: filters.type,
  status: filters.status,
});

export const buildAuditParams = (filters = DEFAULT_AUDIT_FILTERS) => ({
  action: filters.action,
  actor_role: filters.actorRole,
});

export const downloadBlob = (blobData, filename) => {
  const url = window.URL.createObjectURL(new Blob([blobData], { type: "text/csv" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export const apiPath = (path) => `${API}${path}`;