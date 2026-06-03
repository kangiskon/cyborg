import { useCallback, useState } from "react";
import axios from "axios";
import { Bell, ClipboardList, Download, Headphones, Inbox, LockKeyhole, PhoneCall } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { AUDIT_ACTIONS, AUDIT_ROLES, EMPTY_LEAD, EMPTY_STAFF_LOGIN, ICON_SIZE, NOTIFICATION_STATUSES, NOTIFICATION_TYPES } from "@/constants/reception";
import { apiPath, authHeaders } from "@/utils/reception";

export function LeadPanel({ refreshDashboard }) {
  const [lead, setLead] = useState(EMPTY_LEAD);
  const [submitting, setSubmitting] = useState(false);
  const updateLead = (field, value) => setLead((current) => ({ ...current, [field]: value }));
  const submitLead = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await axios.post(apiPath("/leads"), lead);
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
      <div className="panel-heading compact"><div><span data-testid="lead-panel-kicker">Callback queue</span><h2 data-testid="lead-panel-title">Capture lead details</h2></div><PhoneCall data-testid="lead-panel-icon" size={ICON_SIZE.panel} /></div>
      <form className="lead-form" data-testid="lead-capture-form" onSubmit={submitLead}>
        <Input data-testid="lead-name-input" placeholder="Full name" value={lead.name} onChange={(event) => updateLead("name", event.target.value)} required />
        <Input data-testid="lead-phone-input" placeholder="Phone number" value={lead.phone} onChange={(event) => updateLead("phone", event.target.value)} required />
        <Input data-testid="lead-email-input" placeholder="Email, optional" type="email" value={lead.email} onChange={(event) => updateLead("email", event.target.value)} />
        <Input data-testid="lead-contact-time-input" placeholder="Preferred callback time" value={lead.preferred_contact_time} onChange={(event) => updateLead("preferred_contact_time", event.target.value)} />
        <Textarea data-testid="lead-interest-input" placeholder="What do they need help with?" value={lead.interest} onChange={(event) => updateLead("interest", event.target.value)} required />
        <Button data-testid="lead-submit-button" className="secondary-action" type="submit" disabled={submitting}><Inbox size={ICON_SIZE.action} /> Save callback request</Button>
      </form>
    </section>
  );
}

export function StaffLoginPanel({ onLogin }) {
  const [form, setForm] = useState(EMPTY_STAFF_LOGIN);
  const [submitting, setSubmitting] = useState(false);
  const submitLogin = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const response = await axios.post(apiPath("/auth/staff-login"), { access_code: form.accessCode });
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
      <div className="panel-heading compact"><div><span data-testid="staff-login-kicker">Protected area</span><h2 data-testid="staff-login-title">Staff login</h2></div><LockKeyhole data-testid="staff-login-icon" size={ICON_SIZE.panel} /></div>
      <p data-testid="staff-login-description">Enter a staff access code to view the receptionist inbox, appointments, and lead handoff details.</p>
      <form className="staff-login-form" data-testid="staff-login-form" onSubmit={submitLogin}>
        <Label data-testid="staff-code-label" htmlFor="staff-access-code">Access code</Label>
        <Input data-testid="staff-code-input" id="staff-access-code" value={form.accessCode} onChange={(event) => setForm({ accessCode: event.target.value })} placeholder="Enter staff access code" type="password" required />
        <Button data-testid="staff-login-submit-button" className="primary-action" type="submit" disabled={submitting}><LockKeyhole size={ICON_SIZE.action} /> Unlock staff inbox</Button>
      </form>
    </section>
  );
}

function StaffBadge({ staffAuth, onLogout }) {
  if (!staffAuth?.staff) return null;
  return <div className="staff-badge" data-testid="staff-session-badge"><div data-testid="staff-session-details"><strong data-testid="staff-session-name">{staffAuth.staff.name}</strong><span data-testid="staff-session-role">{staffAuth.staff.role}</span></div><button data-testid="staff-logout-button" type="button" onClick={onLogout}>Log out</button></div>;
}

function NotificationCenter({ notifications, unreadCount, onMarkRead, staffId, filters, onFiltersChange }) {
  return (
    <div className="notification-center" data-testid="notification-center-panel">
      <div className="mini-heading" data-testid="notification-center-heading"><span><Bell size={ICON_SIZE.action} /> Notifications</span><strong data-testid="notification-unread-count">{unreadCount}</strong></div>
      <div className="filter-row" data-testid="notification-filter-row">
        <select data-testid="notification-type-filter" value={filters.type} onChange={(event) => onFiltersChange({ ...filters, type: event.target.value })}>{NOTIFICATION_TYPES.map((type) => <option data-testid={`notification-type-option-${type}`} key={type} value={type}>{type.replaceAll("_", " ")}</option>)}</select>
        <select data-testid="notification-status-filter" value={filters.status} onChange={(event) => onFiltersChange({ ...filters, status: event.target.value })}>{NOTIFICATION_STATUSES.map((status) => <option data-testid={`notification-status-option-${status}`} key={status} value={status}>{status}</option>)}</select>
      </div>
      {(notifications || []).length === 0 ? <p data-testid="notifications-empty-state">No alerts yet.</p> : notifications.slice(0, 5).map((item) => <button className={`notification-item ${item.read_by?.includes(staffId) ? "read" : "unread"}`} data-testid={`notification-item-${item.id}`} type="button" key={item.id} onClick={() => onMarkRead(item.id)}><strong data-testid={`notification-item-${item.id}-title`}>{item.title}</strong><span data-testid={`notification-item-${item.id}-message`}>{item.message}</span></button>)}
    </div>
  );
}

function AuditLogPanel({ logs, filters, onFiltersChange, onExport }) {
  return (
    <div className="audit-panel" data-testid="audit-log-panel">
      <div className="mini-heading" data-testid="audit-log-heading"><span><ClipboardList size={ICON_SIZE.action} /> Staff activity</span><button className="export-button" data-testid="audit-export-button" type="button" onClick={onExport}><Download size={ICON_SIZE.tiny} /> Export CSV</button></div>
      <div className="filter-row" data-testid="audit-filter-row">
        <select data-testid="audit-action-filter" value={filters.action} onChange={(event) => onFiltersChange({ ...filters, action: event.target.value })}>{AUDIT_ACTIONS.map((action) => <option data-testid={`audit-action-option-${action}`} key={action} value={action}>{action.replaceAll("_", " ")}</option>)}</select>
        <select data-testid="audit-role-filter" value={filters.actorRole} onChange={(event) => onFiltersChange({ ...filters, actorRole: event.target.value })}>{AUDIT_ROLES.map((role) => <option data-testid={`audit-role-option-${role}`} key={role} value={role}>{role}</option>)}</select>
      </div>
      {(logs || []).length === 0 ? <p data-testid="audit-empty-state">No staff activity yet.</p> : logs.slice(0, 8).map((log) => <div className="audit-item" data-testid={`audit-log-item-${log.id}`} key={log.id}><strong data-testid={`audit-log-item-${log.id}-action`}>{log.action.replaceAll("_", " ")}</strong><span data-testid={`audit-log-item-${log.id}-detail`}>{log.actor_name} · {log.resource}</span></div>)}
    </div>
  );
}

function AccessCodeManager({ staffAuth, refreshDashboard }) {
  const [role, setRole] = useState("staff");
  const [newCode, setNewCode] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const submitCodeChange = async (event) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      await axios.patch(apiPath("/auth/access-codes"), {
        role,
        new_access_code: newCode,
      }, {
        headers: authHeaders(staffAuth.token),
      });
      toast.success(`${role} access code updated. Active ${role} sessions must log in again.`);
      setNewCode("");
      refreshDashboard();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not update access code.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="access-code-panel" data-testid="access-code-manager-panel">
      <div className="mini-heading" data-testid="access-code-heading"><span><LockKeyhole size={ICON_SIZE.action} /> Access codes</span></div>
      <form className="access-code-form" data-testid="access-code-form" onSubmit={submitCodeChange}>
        <select data-testid="access-code-role-select" value={role} onChange={(event) => setRole(event.target.value)}>
          <option data-testid="access-code-role-option-staff" value="staff">Staff</option>
          <option data-testid="access-code-role-option-viewer" value="viewer">Viewer</option>
        </select>
        <Input data-testid="access-code-new-input" value={newCode} onChange={(event) => setNewCode(event.target.value)} minLength={6} placeholder="New access code" required />
        <Button data-testid="access-code-submit-button" className="primary-action" type="submit" disabled={submitting}>Update code</Button>
      </form>
    </div>
  );
}

function SuggestedLeadActions({ lead, staffAuth, refreshDashboard }) {
  const canApprove = ["admin", "staff"].includes(staffAuth?.staff?.role);
  const approveLead = useCallback(async () => {
    try {
      await axios.post(apiPath(`/leads/${lead.id}/approve`), {}, { headers: authHeaders(staffAuth.token) });
      toast.success("Suggested lead approved.");
      refreshDashboard();
    } catch (error) {
      toast.error("Could not approve this suggested lead.");
    }
  }, [apiPath, authHeaders, axios, lead.id, refreshDashboard, staffAuth?.token, toast]);
  if (lead.status !== "suggested" || !canApprove) return null;
  return <button data-testid={`lead-approve-button-${lead.id}`} className="approve-lead-button" type="button" onClick={approveLead}>Approve</button>;
}

export function InboxPanel({ dashboard, staffAuth, onLogin, onLogout, notifications, unreadCount, auditLogs, onMarkRead, refreshDashboard, notificationFilters, onNotificationFiltersChange, auditFilters, onAuditFiltersChange, onAuditExport }) {
  if (!staffAuth?.token) return <StaffLoginPanel onLogin={onLogin} />;
  return (
    <section className="inbox-panel" data-testid="operations-inbox-panel">
      <StaffBadge staffAuth={staffAuth} onLogout={onLogout} />
      <div className="panel-heading compact"><div><span data-testid="inbox-panel-kicker">Today’s handoff</span><h2 data-testid="inbox-panel-title">Reception inbox</h2></div><Headphones data-testid="inbox-panel-icon" size={ICON_SIZE.panel} /></div>
      <NotificationCenter notifications={notifications} unreadCount={unreadCount} onMarkRead={onMarkRead} staffId={staffAuth.staff.id} filters={notificationFilters} onFiltersChange={onNotificationFiltersChange} />
      <div className="handoff-list" data-testid="appointments-handoff-list"><h3 data-testid="appointments-handoff-title">Upcoming appointments</h3>{(dashboard?.next_appointments || []).length === 0 ? <p data-testid="appointments-empty-state">No appointments booked yet.</p> : dashboard.next_appointments.map((appointment) => <div data-testid={`appointment-item-${appointment.id}`} className="handoff-item" key={appointment.id}><div><strong data-testid={`appointment-item-${appointment.id}-name`}>{appointment.name}</strong><span data-testid={`appointment-item-${appointment.id}-service`}>{appointment.service}</span></div><time data-testid={`appointment-item-${appointment.id}-time`}>{appointment.date} · {appointment.time}</time></div>)}</div>
      <div className="handoff-list" data-testid="leads-handoff-list"><h3 data-testid="leads-handoff-title">New callback requests</h3>{(dashboard?.recent_leads || []).length === 0 ? <p data-testid="leads-empty-state">No callback requests yet.</p> : dashboard.recent_leads.map((item) => <div data-testid={`lead-item-${item.id}`} className="handoff-item" key={item.id}><div><strong data-testid={`lead-item-${item.id}-name`}>{item.name}</strong><span data-testid={`lead-item-${item.id}-interest`}>{item.interest}</span></div><div className="lead-meta" data-testid={`lead-item-${item.id}-meta`}><time data-testid={`lead-item-${item.id}-phone`}>{item.phone}</time><span data-testid={`lead-item-${item.id}-status`}>{item.status}</span><SuggestedLeadActions lead={item} staffAuth={staffAuth} refreshDashboard={refreshDashboard} /></div></div>)}</div>
      {staffAuth.staff.role === "admin" && <AccessCodeManager staffAuth={staffAuth} refreshDashboard={refreshDashboard} />}
      {staffAuth.staff.role === "admin" && <AuditLogPanel logs={auditLogs} filters={auditFilters} onFiltersChange={onAuditFiltersChange} onExport={onAuditExport} />}
    </section>
  );
}