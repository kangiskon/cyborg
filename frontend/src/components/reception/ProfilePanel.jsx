import { useCallback, useState } from "react";
import axios from "axios";
import { Building2 } from "lucide-react";
import { toast } from "sonner";
import { Input } from "@/components/ui/input";
import { ICON_SIZE } from "@/constants/reception";
import { apiPath, authHeaders, toTestId } from "@/utils/reception";

function EditableProfileValue({ field, value, editing, canEdit, onStartEdit, onSave, testId }) {
  if (editing === field) {
    return <Input data-testid={`${testId}-input`} autoFocus defaultValue={value} onBlur={(event) => onSave(field, event.target.value)} onKeyDown={(event) => event.key === "Enter" && onSave(field, event.currentTarget.value)} />;
  }
  if (canEdit) {
    return <button data-testid={`${testId}-button`} type="button" onClick={() => onStartEdit(field)}>{value}</button>;
  }
  return <strong data-testid={`${testId}-readonly`}>{value}</strong>;
}

export function ProfilePanel({ profile, setProfile, staffAuth }) {
  const [editing, setEditing] = useState(null);
  const canEditProfile = staffAuth?.staff?.role === "admin";
  const token = staffAuth?.token;

  const saveProfileField = useCallback(async (field, value) => {
    const nextProfile = { ...profile, [field]: value };
    setProfile(nextProfile);
    setEditing(null);
    try {
      await axios.patch(apiPath("/business-profile"), { [field]: value }, { headers: authHeaders(token) });
      toast.success("Business profile updated.");
    } catch (error) {
      toast.error("Could not update profile.");
    }
  }, [apiPath, authHeaders, axios, profile, setEditing, setProfile, toast, token]);

  if (!profile) return null;

  return (
    <section className="profile-panel" data-testid="business-profile-panel">
      <div className="panel-heading compact"><div><span data-testid="profile-panel-kicker">Reception knowledge</span><h2 data-testid="profile-panel-title">Business profile</h2></div><Building2 data-testid="profile-panel-icon" size={ICON_SIZE.panel} /></div>
      <div className="profile-stack" data-testid="profile-field-list">
        <div className="profile-field" data-testid="profile-business-name-field"><span data-testid="profile-business-name-label">Business</span><EditableProfileValue field="business_name" value={profile.business_name} editing={editing} canEdit={canEditProfile} onStartEdit={setEditing} onSave={saveProfileField} testId="profile-business-name" /></div>
        <div className="profile-field" data-testid="profile-hours-field"><span data-testid="profile-hours-label">Hours</span><EditableProfileValue field="hours" value={profile.hours} editing={editing} canEdit={canEditProfile} onStartEdit={setEditing} onSave={saveProfileField} testId="profile-hours" /></div>
        <div className="service-pills" data-testid="profile-service-pill-list">{profile.business_types.map((type) => <span data-testid={`profile-business-type-${toTestId(type)}`} key={type}>{type}</span>)}</div>
        <div className="faq-mini" data-testid="profile-faq-list">{profile.faq.slice(0, 3).map((item, index) => <details data-testid={`profile-faq-item-${index}`} key={item.question}><summary data-testid={`profile-faq-item-${index}-question`}>{item.question}</summary><p data-testid={`profile-faq-item-${index}-answer`}>{item.answer}</p></details>)}</div>
      </div>
    </section>
  );
}