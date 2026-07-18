"use client";

import Link from "next/link";
import { ChangeEvent, useEffect, useState } from "react";
import { api } from "../../lib/api";
import type { AutomationPreferences, UserAppSettings, WorkingDay } from "../../lib/api";
import {
  SETTINGS_KEY,
  defaultSettings as defaults,
  loadAppSettings,
  saveAppSettings,
} from "../../lib/settings";
import type { AppSettings as SettingsState } from "../../lib/settings";

type SettingIconName = "user" | "sliders" | "spark" | "link" | "bell" | "shield" | "card" | "upload" | "sun" | "moon" | "monitor" | "calendar";

type EditableAutomationPreferences = Omit<AutomationPreferences, "id" | "user_id" | "created_at" | "updated_at">;

const defaultAutomationPreferences: EditableAutomationPreferences = {
  timezone: "Asia/Singapore",
  morning_reminder_time: "08:00",
  evening_review_time: "21:00",
  notification_channel: "email",
  telegram_chat_id: null,
  automatic_rescheduling_enabled: false,
  confirmation_required: true,
  max_reminders_per_day: 3,
  quiet_hours_start: "22:00",
  quiet_hours_end: "07:00",
  working_days: ["monday", "tuesday", "wednesday", "thursday", "friday"],
  preferred_study_periods: [],
};

const workingDayOptions: { value: WorkingDay; label: string }[] = [
  { value: "monday", label: "Mon" },
  { value: "tuesday", label: "Tue" },
  { value: "wednesday", label: "Wed" },
  { value: "thursday", label: "Thu" },
  { value: "friday", label: "Fri" },
  { value: "saturday", label: "Sat" },
  { value: "sunday", label: "Sun" },
];

function editableAutomationPreferences(value: AutomationPreferences): EditableAutomationPreferences {
  return {
    timezone: value.timezone,
    morning_reminder_time: value.morning_reminder_time.slice(0, 5),
    evening_review_time: value.evening_review_time.slice(0, 5),
    notification_channel: value.notification_channel,
    telegram_chat_id: value.telegram_chat_id,
    automatic_rescheduling_enabled: value.automatic_rescheduling_enabled,
    confirmation_required: value.confirmation_required,
    max_reminders_per_day: value.max_reminders_per_day,
    quiet_hours_start: value.quiet_hours_start.slice(0, 5),
    quiet_hours_end: value.quiet_hours_end.slice(0, 5),
    working_days: value.working_days,
    preferred_study_periods: value.preferred_study_periods.map((period) => ({
      start: period.start.slice(0, 5),
      end: period.end.slice(0, 5),
    })),
  };
}

function mergeBackendAppSettings(
  current: SettingsState,
  saved: UserAppSettings,
): SettingsState {
  return {
    ...current,
    weekStart: saved.week_start,
    focusMinutes: String(saved.focus_minutes),
    shortBreak: String(saved.short_break_minutes),
    longBreak: String(saved.long_break_minutes),
    cycleCount: String(saved.cycle_count),
    workload: saved.workload,
    theme: saved.theme,
    tone: saved.tone,
    strictness: saved.strictness,
    adjustment: saved.adjustment,
    proactive: saved.proactive,
    focusMatters: saved.focus_matters,
    protectDeepWork: saved.protect_deep_work,
    learnFromFeedback: saved.learn_from_feedback,
    integrations: saved.integrations,
  };
}

function backendAppSettingsPayload(
  value: SettingsState,
  avatarDataUrl: string,
): Omit<UserAppSettings, "id" | "user_id" | "created_at" | "updated_at"> {
  return {
    week_start: value.weekStart as "Monday" | "Sunday",
    focus_minutes: Number(value.focusMinutes) as 25 | 45 | 60,
    short_break_minutes: Number(value.shortBreak) as 5 | 10,
    long_break_minutes: Number(value.longBreak) as 15 | 30,
    cycle_count: Math.min(12, Math.max(1, Number(value.cycleCount) || 4)),
    workload: value.workload as "light" | "medium" | "high",
    theme: value.theme,
    tone: value.tone as "supportive" | "direct" | "reflective",
    strictness: value.strictness as "flexible" | "balanced" | "strict",
    adjustment: value.adjustment as "gentle" | "moderate" | "strong",
    proactive: value.proactive,
    focus_matters: value.focusMatters,
    protect_deep_work: value.protectDeepWork,
    learn_from_feedback: value.learnFromFeedback,
    integrations: value.integrations as UserAppSettings["integrations"],
    avatar_data_url: avatarDataUrl || null,
  };
}

function SettingIcon({ name, size = 19 }: { name: SettingIconName; size?: number }) {
  const paths: Record<SettingIconName, React.ReactNode> = {
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    sliders: <><path d="M4 6h7M15 6h5M4 12h3M11 12h9M4 18h9M17 18h3" /><circle cx="13" cy="6" r="2" /><circle cx="9" cy="12" r="2" /><circle cx="15" cy="18" r="2" /></>,
    spark: <path d="m12 2 1.6 5.1a5 5 0 0 0 3.3 3.3L22 12l-5.1 1.6a5 5 0 0 0-3.3 3.3L12 22l-1.6-5.1a5 5 0 0 0-3.3-3.3L2 12l5.1-1.6a5 5 0 0 0 3.3-3.3L12 2Z" />,
    link: <><path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1.2 1.2" /><path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1.2-1.2" /></>,
    bell: <><path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" /><path d="M10 21h4" /></>,
    shield: <><path d="M12 2 4 5v6c0 5 3.4 8.7 8 11 4.6-2.3 8-6 8-11V5l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
    card: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 10h18" /></>,
    upload: <><path d="M12 16V4M8 8l4-4 4 4" /><path d="M4 14v6h16v-6" /></>,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M19 5l-1.5 1.5M6.5 17.5 5 19" /></>,
    moon: <path d="M20 15.2A8.5 8.5 0 0 1 8.8 4a8.5 8.5 0 1 0 11.2 11.2Z" />,
    monitor: <><rect x="3" y="4" width="18" height="13" rx="2" /><path d="M8 21h8M12 17v4" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M16 3v4M8 3v4M3 10h18" /></>,
  };
  return <svg aria-hidden="true" className="setting-icon" fill="none" height={size} viewBox="0 0 24 24" width={size}>{paths[name]}</svg>;
}

const settingNav: { id: string; label: string; hint: string; icon: SettingIconName }[] = [
  { id: "profile", label: "Profile", hint: "Your account and basic info", icon: "user" },
  { id: "preferences", label: "Preferences", hint: "General app preferences", icon: "sliders" },
  { id: "ai-coach", label: "AI Coach", hint: "Coach behavior and style", icon: "spark" },
  { id: "integrations", label: "Integrations", hint: "Connect your tools", icon: "link" },
  { id: "notifications", label: "Notifications", hint: "Manage alerts and reminders", icon: "bell" },
  { id: "data", label: "Privacy & Data", hint: "Data, privacy and export", icon: "shield" },
  { id: "subscription", label: "Subscription", hint: "Manage your plan", icon: "card" },
];

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsState>(defaults);
  const [activeSection, setActiveSection] = useState("profile");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [message, setMessage] = useState("");
  const [automation, setAutomation] = useState<EditableAutomationPreferences>(defaultAutomationPreferences);
  const [savingAll, setSavingAll] = useState(false);
  const [testingEmail, setTestingEmail] = useState(false);
  const [testingTelegram, setTestingTelegram] = useState(false);

  useEffect(() => {
    setSettings(loadAppSettings());
    api.getCurrentUser()
      .then((user) => {
        setSettings((current) => ({
          ...current,
          name: user.display_name || "",
          email: user.email,
        }));
      })
      .catch((error: Error) => setMessage(`Could not load profile: ${error.message}`));
    api.getAutomationPreferences()
      .then((value) => {
        const saved = editableAutomationPreferences(value);
        setAutomation(saved);
        setSettings((current) => ({ ...current, timezone: saved.timezone }));
      })
      .catch((error: Error) => setMessage(`Could not load automation preferences: ${error.message}`));
    api.getAppSettings()
      .then((saved) => {
        setSettings((current) => mergeBackendAppSettings(current, saved));
        setAvatarUrl(saved.avatar_data_url || "");
      })
      .catch((error: Error) => setMessage(`Could not load app settings: ${error.message}`));
  }, []);

  function update<K extends keyof SettingsState>(key: K, value: SettingsState[K]) {
    setSettings((current) => ({ ...current, [key]: value }));
    setMessage("You have unsaved settings changes.");
  }

  async function saveAllSettings() {
    setSavingAll(true);
    try {
      const [user, savedAutomation, savedAppSettings] = await Promise.all([
        api.updateCurrentUser({
          display_name: settings.name.trim(),
          email: settings.email.trim(),
        }),
        api.updateAutomationPreferences({
          ...automation,
          timezone: settings.timezone,
        }),
        api.updateAppSettings(backendAppSettingsPayload(settings, avatarUrl)),
      ]);
      const synchronized = mergeBackendAppSettings(
        {
          ...settings,
          name: user.display_name || "",
          email: user.email,
          timezone: savedAutomation.timezone,
        },
        savedAppSettings,
      );
      setSettings(synchronized);
      setAutomation(editableAutomationPreferences(savedAutomation));
      saveAppSettings(synchronized);
      setMessage("All settings were saved to the frontend and backend.");
    } catch (error) {
      setMessage(`Could not save all settings: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setSavingAll(false);
    }
  }

  function updateAutomation<K extends keyof EditableAutomationPreferences>(
    key: K,
    value: EditableAutomationPreferences[K],
  ) {
    setAutomation((current) => ({ ...current, [key]: value }));
    setMessage("You have unsaved settings changes.");
  }

  function toggleWorkingDay(day: WorkingDay) {
    const selected = automation.working_days.includes(day);
    if (selected && automation.working_days.length === 1) {
      setMessage("At least one working day is required.");
      return;
    }
    updateAutomation(
      "working_days",
      selected
        ? automation.working_days.filter((value) => value !== day)
        : [...automation.working_days, day],
    );
  }

  function addStudyPeriod() {
    if (automation.preferred_study_periods.length >= 5) return;
    updateAutomation("preferred_study_periods", [
      ...automation.preferred_study_periods,
      { start: "19:00", end: "21:00" },
    ]);
  }

  function changeAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 1_500_000) {
      setMessage("Avatar must be smaller than 1.5 MB.");
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      setAvatarUrl(String(reader.result));
      setMessage("You have unsaved settings changes.");
    };
    reader.readAsDataURL(file);
  }

  function toggleIntegration(name: string) {
    update("integrations", settings.integrations.includes(name) ? settings.integrations.filter((item) => item !== name) : [...settings.integrations, name]);
  }

  async function testEmailNotification() {
    setTestingEmail(true);
    try {
      const delivery = await api.sendTestEmail();
      if (delivery.status === "delivered") {
        setMessage(`Test email delivered to ${delivery.recipient}.`);
      } else if (delivery.status === "failed") {
        setMessage(`Test email failed: ${delivery.failure_reason || "Unknown SMTP error"}`);
      } else {
        setMessage(`Test email is ${delivery.status}.`);
      }
    } catch (error) {
      setMessage(`Could not test email: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setTestingEmail(false);
    }
  }

  async function testTelegramNotification() {
    setTestingTelegram(true);
    try {
      const delivery = await api.sendTestTelegram();
      if (delivery.status === "delivered") {
        setMessage("Test Telegram message delivered.");
      } else if (delivery.status === "failed") {
        setMessage(`Test Telegram failed: ${delivery.failure_reason || "Unknown Telegram error"}`);
      } else {
        setMessage(`Test Telegram message is ${delivery.status}.`);
      }
    } catch (error) {
      setMessage(`Could not test Telegram: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setTestingTelegram(false);
    }
  }

  function exportSettings() {
    const payload = JSON.stringify({ settings, avatarDataUrl: avatarUrl || null }, null, 2);
    const url = URL.createObjectURL(new Blob([payload], { type: "application/json" }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "ai-life-settings.json";
    anchor.click();
    URL.revokeObjectURL(url);
    setMessage("Settings export created.");
  }

  function importSettings(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as { settings?: Partial<SettingsState>; avatarDataUrl?: string | null };
        if (parsed.settings) setSettings({ ...defaults, ...parsed.settings });
        if (parsed.avatarDataUrl !== undefined) setAvatarUrl(parsed.avatarDataUrl || "");
        setMessage("Settings imported successfully.");
      } catch {
        setMessage("That file is not a valid AI Life settings export.");
      }
    };
    reader.readAsText(file);
  }

  function clearLocalSettings() {
    if (!window.confirm("Clear locally saved preferences and restore defaults? Backend tasks and reviews will not be deleted.")) return;
    window.localStorage.removeItem(SETTINGS_KEY);
    setSettings(defaults);
    setAvatarUrl("");
    setMessage("Local preferences were reset. Backend data was not deleted.");
  }

  function scrollTo(id: string) {
    setActiveSection(id);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  return (
    <section className="settings-workspace">
      <header className="settings-header"><div><h1>Settings</h1><p>Customize your experience and AI coach to fit your goals.</p></div><div><Link aria-label="Open calendar" href="/today"><SettingIcon name="calendar" /></Link><Link className="settings-coach-button" href="/check-in"><SettingIcon name="spark" /> Ask my coach <span>⌄</span></Link></div></header>
      {message ? <div className="settings-message">{message}<button onClick={() => setMessage("")} type="button">×</button></div> : null}

      <div className="settings-layout">
        <aside className="settings-section-nav">{settingNav.map((item) => <button className={activeSection === item.id ? "active" : ""} key={item.id} onClick={() => scrollTo(item.id)} type="button"><SettingIcon name={item.icon} /><span><strong>{item.label}</strong><small>{item.hint}</small></span></button>)}<div className="settings-nav-save"><button disabled={savingAll} onClick={saveAllSettings} type="button">{savingAll ? "Saving..." : "Save profile"}</button><small>Saves all settings</small></div></aside>

        <main className="settings-panels">
          <section className="settings-card profile-settings" id="profile"><h2>Profile</h2><div className="settings-profile-grid"><div className="settings-fields"><label>Name<input value={settings.name} onChange={(event) => update("name", event.target.value)} /></label><label>Email<input type="email" value={settings.email} onChange={(event) => update("email", event.target.value)} /></label><label>Telegram chat ID<input inputMode="numeric" placeholder="Example: 123456789" value={automation.telegram_chat_id || ""} onChange={(event) => updateAutomation("telegram_chat_id", event.target.value || null)} /></label></div><div className="settings-fields"><label>Avatar<span className="avatar-control"><i style={avatarUrl ? { backgroundImage: `url(${avatarUrl})` } : undefined}>{avatarUrl ? "" : settings.name.slice(0, 2).toUpperCase()}</i><b><SettingIcon name="upload" size={14} /> Change<input accept="image/*" onChange={changeAvatar} type="file" /></b></span></label><label>Time Zone<select value={settings.timezone} onChange={(event) => update("timezone", event.target.value)}><option value="Asia/Singapore">(UTC+08:00) Beijing, Shanghai, Singapore</option><option value="Europe/London">(UTC+00:00) London</option><option value="America/New_York">(UTC-05:00) New York</option><option value="America/Los_Angeles">(UTC-08:00) Los Angeles</option></select></label></div></div></section>

          <section className="settings-card" id="preferences"><h2>Preferences</h2><div className="preference-grid"><label>Week starts on<select value={settings.weekStart} onChange={(event) => update("weekStart", event.target.value)}><option>Monday</option><option>Sunday</option></select></label><div className="theme-field"><span>Theme</span><div>{(["light", "dark", "auto"] as const).map((theme) => <button className={settings.theme === theme ? "active" : ""} key={theme} onClick={() => update("theme", theme)} type="button"><SettingIcon name={theme === "light" ? "sun" : theme === "dark" ? "moon" : "monitor"} size={15} /> {theme[0].toUpperCase() + theme.slice(1)}</button>)}</div></div></div></section>

          <section className="settings-card" id="ai-coach"><h2>AI Coach</h2><div className="coach-settings-grid"><label>Coaching tone<select value={settings.tone} onChange={(event) => update("tone", event.target.value)}><option value="supportive">Supportive</option><option value="direct">Direct</option><option value="reflective">Reflective</option></select></label><label>Planning strictness<select value={settings.strictness} onChange={(event) => update("strictness", event.target.value)}><option value="flexible">Flexible</option><option value="balanced">Balanced</option><option value="strict">Strict</option></select></label><label>Workload adjustment<select value={settings.adjustment} onChange={(event) => update("adjustment", event.target.value)}><option value="gentle">Gentle</option><option value="moderate">Moderate</option><option value="strong">Strong</option></select></label><label className="switch-setting"><span>Proactive reminders</span><button aria-pressed={settings.proactive} className={settings.proactive ? "on" : ""} onClick={() => update("proactive", !settings.proactive)} type="button"><i /></button><small>AI will proactively remind and suggest.</small></label></div><div className="coach-checkboxes"><label>Focus on what matters most<span><input checked={settings.focusMatters} onChange={(event) => update("focusMatters", event.target.checked)} type="checkbox" /> AI helps me focus on high-impact tasks.</span></label><label>Protect deep work time<span><input checked={settings.protectDeepWork} onChange={(event) => update("protectDeepWork", event.target.checked)} type="checkbox" /> Block interruptions during focus sessions.</span></label><label>Learning from feedback<span><input checked={settings.learnFromFeedback} onChange={(event) => update("learnFromFeedback", event.target.checked)} type="checkbox" /> AI learns from your reviews and check-ins.</span></label></div></section>

          <section className="settings-card" id="integrations"><h2>Integrations</h2><div className="integration-grid">{[{ name: "Google Calendar", mark: "G", hint: "Sync your schedule and tasks." }, { name: "Notion", mark: "N", hint: "Sync tasks and notes." }, { name: "Telegram", mark: "T", hint: "Test delivery using your saved chat ID." }, { name: "Gmail", mark: "M", hint: "Test delivery to your saved profile email." }].map((item) => { const connected = settings.integrations.includes(item.name); return <article key={item.name}><i>{item.mark}</i><div><strong>{item.name}</strong><span>{item.hint}</span></div><b>›</b><span className="integration-actions"><button className={connected ? "connected" : ""} onClick={() => toggleIntegration(item.name)} type="button">{connected ? "Connected" : "Connect"}</button>{item.name === "Gmail" ? <button disabled={testingEmail} onClick={testEmailNotification} type="button">{testingEmail ? "Testing..." : "Test email"}</button> : null}{item.name === "Telegram" ? <button disabled={testingTelegram} onClick={testTelegramNotification} type="button">{testingTelegram ? "Testing..." : "Test Telegram"}</button> : null}</span></article>; })}</div></section>

          <section className="settings-card notifications-card" id="notifications">
            <h2>Automation & Notifications</h2>
            <p>These saved preferences constrain future reminders and scheduling actions. Step 1 safety rules always take priority.</p>
            <div className="preference-grid">
              <label>Morning reminder time<input type="time" value={automation.morning_reminder_time} onChange={(event) => updateAutomation("morning_reminder_time", event.target.value)} /></label>
              <label>Evening review time<input type="time" value={automation.evening_review_time} onChange={(event) => updateAutomation("evening_review_time", event.target.value)} /></label>
              <label>Notification channel<select value={automation.notification_channel} onChange={(event) => updateAutomation("notification_channel", event.target.value as EditableAutomationPreferences["notification_channel"])}><option value="email">Email</option><option value="telegram">Telegram</option><option disabled value="in_app">In app (coming later)</option></select></label>
              <label>Maximum reminders per day<input min="0" max="20" type="number" value={automation.max_reminders_per_day} onChange={(event) => updateAutomation("max_reminders_per_day", Number(event.target.value))} /></label>
              <label>Quiet hours start<input type="time" value={automation.quiet_hours_start} onChange={(event) => updateAutomation("quiet_hours_start", event.target.value)} /></label>
              <label>Quiet hours end<input type="time" value={automation.quiet_hours_end} onChange={(event) => updateAutomation("quiet_hours_end", event.target.value)} /></label>
              <label className="switch-setting"><span>Automatic rescheduling</span><button aria-pressed={automation.automatic_rescheduling_enabled} className={automation.automatic_rescheduling_enabled ? "on" : ""} onClick={() => updateAutomation("automatic_rescheduling_enabled", !automation.automatic_rescheduling_enabled)} type="button"><i /></button><small>Allows approved rescheduling workflows to run.</small></label>
              <label className="switch-setting"><span>Extra confirmation preference</span><button aria-pressed={automation.confirmation_required} className={automation.confirmation_required ? "on" : ""} onClick={() => updateAutomation("confirmation_required", !automation.confirmation_required)} type="button"><i /></button><small>Mandatory Step 1 confirmations cannot be disabled.</small></label>
            </div>
            <div className="coach-checkboxes">
              <label>Working days<span>{workingDayOptions.map((day) => <label key={day.value}><input checked={automation.working_days.includes(day.value)} onChange={() => toggleWorkingDay(day.value)} type="checkbox" /> {day.label}</label>)}</span></label>
              <label>Preferred study periods<span>{automation.preferred_study_periods.length === 0 ? <small>No preferred periods set.</small> : automation.preferred_study_periods.map((period, index) => <span key={`${index}-${period.start}`}><input aria-label={`Study period ${index + 1} start`} type="time" value={period.start} onChange={(event) => updateAutomation("preferred_study_periods", automation.preferred_study_periods.map((item, itemIndex) => itemIndex === index ? { ...item, start: event.target.value } : item))} /><input aria-label={`Study period ${index + 1} end`} type="time" value={period.end} onChange={(event) => updateAutomation("preferred_study_periods", automation.preferred_study_periods.map((item, itemIndex) => itemIndex === index ? { ...item, end: event.target.value } : item))} /><button onClick={() => updateAutomation("preferred_study_periods", automation.preferred_study_periods.filter((_, itemIndex) => itemIndex !== index))} type="button">Remove</button></span>)}<button disabled={automation.preferred_study_periods.length >= 5} onClick={addStudyPeriod} type="button">Add period</button></span></label>
            </div>
          </section>

          <section className="settings-card data-settings" id="data"><h2>Data & Export</h2><div><article><span><strong>Export settings</strong><small>Download your preferences and profile.</small></span><button onClick={exportSettings} type="button">Export</button></article><article><span><strong>Import settings</strong><small>Import a previous settings export.</small></span><label>Import<input accept="application/json" onChange={importSettings} type="file" /></label></article><article className="danger"><span><strong>Reset local settings</strong><small>Backend tasks and reviews will remain safe.</small></span><button onClick={clearLocalSettings} type="button">Reset</button></article></div></section>

          <section className="settings-card subscription-card" id="subscription"><h2>Subscription</h2><p>AI Life MVP workspace</p><span>Local development plan</span></section>
        </main>
      </div>
    </section>
  );
}
