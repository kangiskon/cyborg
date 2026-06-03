import { useCallback, useEffect, useMemo, useState } from "react";
import "@/App.css";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import axios from "axios";
import { ArrowRight, Bot, Clock3, Sparkles } from "lucide-react";
import { Toaster, toast } from "sonner";
import { BookingPanel } from "@/components/reception/BookingPanel";
import { ChatPanel } from "@/components/reception/ChatPanel";
import { InboxPanel, LeadPanel } from "@/components/reception/StaffPanels";
import { ProfilePanel } from "@/components/reception/ProfilePanel";
import {
  DEFAULT_AUDIT_FILTERS,
  DEFAULT_NOTIFICATION_FILTERS,
  HTTP_STATUS,
  ICON_SIZE,
  initialMessage,
} from "@/constants/reception";
import {
  apiPath,
  authHeaders,
  buildAuditParams,
  buildNotificationParams,
  buildStats,
  clearStaffState,
  downloadBlob,
} from "@/utils/reception";

function StatTile({ icon: Icon, label, value, detail, testId }) {
  return (
    <div data-testid={testId} className="stat-tile">
      <div className="stat-icon" data-testid={`${testId}-icon`}><Icon size={ICON_SIZE.stat} /></div>
      <p data-testid={`${testId}-label`}>{label}</p>
      <strong data-testid={`${testId}-value`}>{value}</strong>
      <span data-testid={`${testId}-detail`}>{detail}</span>
    </div>
  );
}

function useReceptionData() {
  const [profile, setProfile] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [staffAuth, setStaffAuth] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [auditLogs, setAuditLogs] = useState([]);
  const [notificationFilters, setNotificationFilters] = useState(DEFAULT_NOTIFICATION_FILTERS);
  const [auditFilters, setAuditFilters] = useState(DEFAULT_AUDIT_FILTERS);

  const resetStaffState = useCallback(() => {
    clearStaffState({ setStaffAuth, setDashboard, setNotifications, setUnreadCount, setAuditLogs });
  }, [clearStaffState]);

  const loadPublicData = useCallback(async () => {
    try {
      const response = await axios.get(apiPath("/business-profile"));
      setProfile(response.data);
    } catch (error) {
      toast.error("Could not load receptionist workspace.");
    }
  }, [apiPath, axios, setProfile, toast]);

  const loadProtectedData = useCallback(async (token, filters) => {
    if (!token) {
      setDashboard(null);
      return;
    }
    try {
      const headers = authHeaders(token);
      const [dashboardResponse, notificationResponse, meResponse] = await Promise.all([
        axios.get(apiPath("/dashboard"), { headers }),
        axios.get(apiPath("/notifications"), { headers, params: buildNotificationParams(filters.notification) }),
        axios.get(apiPath("/auth/me"), { headers }),
      ]);
      setDashboard(dashboardResponse.data);
      setNotifications(notificationResponse.data.notifications);
      setUnreadCount(notificationResponse.data.unread_count);

      if (meResponse.data.role === "admin") {
        const auditResponse = await axios.get(apiPath("/audit-logs"), { headers, params: buildAuditParams(filters.audit) });
        setAuditLogs(auditResponse.data.logs);
      } else {
        setAuditLogs([]);
      }
    } catch (error) {
      const status = error.response?.status;
      if ([HTTP_STATUS.unauthorized, HTTP_STATUS.forbidden].includes(status)) {
        resetStaffState();
        toast.error("Staff session expired. Please log in again.");
      } else {
        toast.error("Could not load staff inbox.");
      }
    }
  }, [HTTP_STATUS, apiPath, authHeaders, axios, buildAuditParams, buildNotificationParams, resetStaffState, setAuditLogs, setDashboard, setNotifications, setUnreadCount, toast]);

  return {
    profile,
    setProfile,
    dashboard,
    staffAuth,
    setStaffAuth,
    notifications,
    unreadCount,
    auditLogs,
    notificationFilters,
    setNotificationFilters,
    auditFilters,
    setAuditFilters,
    resetStaffState,
    loadPublicData,
    loadProtectedData,
  };
}

function Home() {
  const [messages, setMessages] = useState([initialMessage]);
  const [sessionId, setSessionId] = useState(null);
  const {
    profile,
    setProfile,
    dashboard,
    staffAuth,
    setStaffAuth,
    notifications,
    unreadCount,
    auditLogs,
    notificationFilters,
    setNotificationFilters,
    auditFilters,
    setAuditFilters,
    resetStaffState,
    loadPublicData,
    loadProtectedData,
  } = useReceptionData();

  const activeFilters = useMemo(() => ({ notification: notificationFilters, audit: auditFilters }), [notificationFilters, auditFilters]);
  const stats = useMemo(() => buildStats(dashboard), [dashboard, buildStats]);

  useEffect(() => { loadPublicData(); }, [loadPublicData]);
  useEffect(() => {
    const token = staffAuth?.token;
    if (token) loadProtectedData(token, activeFilters);
  }, [activeFilters, loadProtectedData, staffAuth?.token]);

  const handleStaffLogin = useCallback((nextStaffAuth) => {
    setStaffAuth(nextStaffAuth);
    loadProtectedData(nextStaffAuth.token, activeFilters);
  }, [activeFilters, loadProtectedData, setStaffAuth]);

  const handleStaffLogout = useCallback(() => {
    const token = staffAuth?.token;
    if (token) axios.post(apiPath("/auth/logout"), {}, { headers: authHeaders(token) }).catch(() => {});
    resetStaffState();
    setNotificationFilters(DEFAULT_NOTIFICATION_FILTERS);
    setAuditFilters(DEFAULT_AUDIT_FILTERS);
    toast.success("Staff logged out.");
  }, [DEFAULT_AUDIT_FILTERS, DEFAULT_NOTIFICATION_FILTERS, apiPath, authHeaders, axios, resetStaffState, setAuditFilters, setNotificationFilters, staffAuth?.token, toast]);

  const refreshDashboard = useCallback(() => {
    loadProtectedData(staffAuth?.token, activeFilters);
  }, [activeFilters, loadProtectedData, staffAuth?.token]);

  const markNotificationRead = useCallback(async (notificationId) => {
    const token = staffAuth?.token;
    if (!token) return;
    try {
      await axios.post(apiPath(`/notifications/${notificationId}/read`), {}, { headers: authHeaders(token) });
      refreshDashboard();
    } catch (error) {
      toast.error("Could not mark notification as read.");
    }
  }, [apiPath, authHeaders, axios, refreshDashboard, staffAuth?.token, toast]);

  const exportAuditLogs = useCallback(async () => {
    const token = staffAuth?.token;
    if (!token) return;
    try {
      const response = await axios.get(apiPath("/audit-logs/export"), { headers: authHeaders(token), params: buildAuditParams(auditFilters), responseType: "blob" });
      downloadBlob(response.data, "frontkind-audit-export.csv");
      toast.success("Audit CSV exported.");
      refreshDashboard();
    } catch (error) {
      toast.error("Could not export audit logs.");
    }
  }, [apiPath, auditFilters, authHeaders, axios, buildAuditParams, downloadBlob, refreshDashboard, staffAuth?.token, toast]);

  return (
    <div className="reception-app" data-testid="ai-receptionist-app">
      <Toaster richColors position="top-right" />
      <nav className="top-nav" data-testid="top-navigation">
        <a data-testid="brand-home-link" href="/" className="brand-mark"><span data-testid="brand-icon"><Sparkles size={ICON_SIZE.action} /></span><strong data-testid="brand-name">Frontkind</strong></a>
        <div className="nav-actions" data-testid="navigation-actions"><a data-testid="nav-chat-link" href="#chat">Reception</a><a data-testid="nav-booking-link" href="#booking">Booking</a><a data-testid="nav-inbox-link" href="#inbox">Inbox</a></div>
      </nav>
      <main data-testid="main-workspace">
        <section className="hero-band" data-testid="hero-section">
          <div className="hero-copy" data-testid="hero-copy"><span className="eyebrow" data-testid="hero-eyebrow"><Clock3 size={ICON_SIZE.tiny} /> Always-on front desk</span><h1 data-testid="hero-title">A calm AI receptionist for every small business front door.</h1><p data-testid="hero-subtitle">Answer questions, collect warm leads, and confirm appointments from one focused reception workspace.</p><div className="hero-actions" data-testid="hero-actions"><a data-testid="hero-start-chat-link" href="#chat" className="hero-primary">Start greeting visitors <ArrowRight size={ICON_SIZE.action} /></a><a data-testid="hero-booking-link" href="#booking" className="hero-secondary">Open booking desk</a></div></div>
          <div className="hero-visual" data-testid="hero-visual"><img data-testid="hero-background-image" src="https://images.unsplash.com/photo-1773924093206-9a433a14bb44?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85" alt="Warm reception interior" /><div className="hero-cardlet" data-testid="hero-live-cardlet"><Bot size={ICON_SIZE.cardlet} /><span data-testid="hero-live-cardlet-text">Greeting visitor · collecting details</span></div></div>
        </section>
        <section className="stats-grid" data-testid="dashboard-stats-grid">{stats.map((stat) => <StatTile key={stat.testId} {...stat} />)}</section>
        <section className="workspace-grid" data-testid="control-room-grid"><div id="chat" className="workspace-main" data-testid="workspace-main-column"><ChatPanel messages={messages} setMessages={setMessages} sessionId={sessionId} setSessionId={setSessionId} /></div><aside className="workspace-side" data-testid="workspace-side-column"><ProfilePanel profile={profile} setProfile={setProfile} staffAuth={staffAuth} /></aside></section>
        <section id="booking" className="workflow-grid" data-testid="booking-and-lead-grid"><BookingPanel profile={profile} refreshDashboard={refreshDashboard} /><LeadPanel refreshDashboard={refreshDashboard} /></section>
        <section id="inbox" className="inbox-grid" data-testid="inbox-section"><InboxPanel dashboard={dashboard} staffAuth={staffAuth} onLogin={handleStaffLogin} onLogout={handleStaffLogout} notifications={notifications} unreadCount={unreadCount} auditLogs={auditLogs} onMarkRead={markNotificationRead} refreshDashboard={refreshDashboard} notificationFilters={notificationFilters} onNotificationFiltersChange={setNotificationFilters} auditFilters={auditFilters} onAuditFiltersChange={setAuditFilters} onAuditExport={exportAuditLogs} /></section>
      </main>
    </div>
  );
}

function App() {
  return <div className="App" data-testid="app-root"><BrowserRouter><Routes><Route path="/" element={<Home />} /></Routes></BrowserRouter></div>;
}

export default App;
