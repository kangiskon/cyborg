import { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { CalendarCheck, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { DEFAULT_SERVICES, ICON_SIZE } from "@/constants/reception";
import { apiPath, todayIso, toTestId } from "@/utils/reception";

const initialBookingForm = () => ({ name: "", phone: "", email: "", service: "New client consultation", date: todayIso(), time: "", notes: "" });

export function BookingPanel({ profile, refreshDashboard }) {
  const [form, setForm] = useState(initialBookingForm);
  const [slots, setSlots] = useState([]);
  const [submitting, setSubmitting] = useState(false);

  const loadSlots = useCallback(async (date) => {
    try {
      const response = await axios.get(apiPath("/appointments/slots"), { params: { date } });
      setSlots(response.data.slots);
      const firstAvailable = response.data.slots.find((slot) => slot.available);
      setForm((current) => ({ ...current, time: firstAvailable?.time || "" }));
    } catch (error) {
      toast.error("Could not load appointment slots.");
    }
  }, []);

  useEffect(() => { loadSlots(form.date); }, [form.date, loadSlots]);

  const updateField = useCallback((field, value) => setForm((current) => ({ ...current, [field]: value })), []);

  const submitBooking = async (event) => {
    event.preventDefault();
    if (!form.time) return toast.error("Please choose an available time.");
    setSubmitting(true);
    try {
      await axios.post(apiPath("/appointments"), form);
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
      <div className="panel-heading compact"><div><span data-testid="booking-panel-kicker">Appointment flow</span><h2 data-testid="booking-panel-title">Book a visit</h2></div><CalendarCheck data-testid="booking-panel-icon" size={ICON_SIZE.panel} /></div>
      <form className="booking-form" data-testid="appointment-booking-form" onSubmit={submitBooking}>
        <div className="form-pair"><Label data-testid="booking-name-label" htmlFor="booking-name">Name</Label><Input data-testid="booking-name-input" id="booking-name" value={form.name} onChange={(event) => updateField("name", event.target.value)} required /></div>
        <div className="form-pair"><Label data-testid="booking-phone-label" htmlFor="booking-phone">Phone</Label><Input data-testid="booking-phone-input" id="booking-phone" value={form.phone} onChange={(event) => updateField("phone", event.target.value)} required /></div>
        <div className="form-pair wide"><Label data-testid="booking-email-label" htmlFor="booking-email">Email</Label><Input data-testid="booking-email-input" id="booking-email" type="email" value={form.email} onChange={(event) => updateField("email", event.target.value)} /></div>
        <div className="form-pair wide"><Label data-testid="booking-service-label" htmlFor="booking-service">Service</Label><select data-testid="booking-service-select" id="booking-service" value={form.service} onChange={(event) => updateField("service", event.target.value)}>{(profile?.services || DEFAULT_SERVICES).map((service) => <option data-testid={`booking-service-option-${toTestId(service)}`} key={service} value={service}>{service}</option>)}</select></div>
        <div className="form-pair"><Label data-testid="booking-date-label" htmlFor="booking-date">Date</Label><Input data-testid="booking-date-input" id="booking-date" type="date" min={todayIso()} value={form.date} onChange={(event) => updateField("date", event.target.value)} required /></div>
        <div className="form-pair"><Label data-testid="booking-time-label" htmlFor="booking-time">Time</Label><select data-testid="booking-time-select" id="booking-time" value={form.time} onChange={(event) => updateField("time", event.target.value)} required><option data-testid="booking-time-option-empty" value="">Choose time</option>{slots.map((slot) => <option data-testid={`booking-time-option-${slot.time.replace(":", "-")}`} key={slot.time} disabled={!slot.available} value={slot.time}>{slot.time} {slot.available ? "" : "— booked"}</option>)}</select></div>
        <div className="form-pair wide"><Label data-testid="booking-notes-label" htmlFor="booking-notes">Notes</Label><Textarea data-testid="booking-notes-input" id="booking-notes" value={form.notes} onChange={(event) => updateField("notes", event.target.value)} placeholder="Anything the team should know?" /></div>
        <Button data-testid="booking-submit-button" className="primary-action" type="submit" disabled={submitting}><Check size={ICON_SIZE.action} /> Confirm appointment</Button>
      </form>
    </section>
  );
}