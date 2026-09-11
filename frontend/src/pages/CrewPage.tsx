import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Bell, CheckCircle2, ClipboardCheck, LogIn, LogOut, UserPlus, UsersRound } from "lucide-react";
import { api, errorMessage } from "../api/client";
import { authConfig, notifyAuthChanged, tokenKey, type AuthUser } from "../auth";

type Language = "en" | "hi";
type Crew = AuthUser;
type WorkOrder = { id: string; work_order_number: string; title: string; section_id: string; required_skill: string; status: string; priority: string; assigned_crew_id?: string | null };
type ActiveCrew = { employee_id: string; full_name: string; primary_skill: string; secondary_skills: string[] };
type Notification = { id: string; title: string; message: string; priority: string; read_at?: string | null };
type PendingCrew = { employee_id: string; full_name: string; email: string; role: string; primary_skill: string; created_at: string };
type Checklist = { id: string; type: string; is_mandatory: boolean; signed_at?: string | null; items: { id: string; text: string; required?: boolean }[]; completed_items: Record<string, { value: boolean; note?: string }> };

const copy = {
  en: { eyebrow: "CREW MANAGEMENT", title: "Field crew workspace", intro: "Manage safe assignments, checklists and notifications in one place.", login: "Sign in", register: "Create crew account", employee: "Employee ID", password: "Password", email: "Work email", name: "Full name", role: "Role", skill: "Primary skill", shiftStart: "Shift starts", shiftEnd: "Shift ends", submitLogin: "Sign in securely", submitRegister: "Submit for approval", pending: "Account submitted. An administrator must approve it before sign-in.", signedIn: "Signed in as", orders: "All work orders", notifications: "Notifications", noOrders: "No work orders assigned yet.", noNotifications: "No notifications.", logout: "Sign out", active: "Active", unread: "Unread", refresh: "Refresh", support: "Safety is always a hard constraint.", approval: "Awaiting administrator approval", loginHint: "Use your approved employee ID and password.", registerHint: "Use a strong password with at least 12 characters.", checklist: "Safety checklist", noChecklist: "No checklist has been created for this order yet.", mandatory: "Mandatory", workerTitle: "Assigned work notifications", workerDescription: "Your account can only view notifications sent by an administrator.", pendingTitle: "Pending crew approvals", pendingDescription: "New registrations require administrator confirmation.", approve: "Approve", approving: "Approving…", dismiss: "Dismiss" },
  hi: { eyebrow: "क्रू प्रबंधन", title: "फील्ड क्रू कार्यक्षेत्र", intro: "सुरक्षित असाइनमेंट, चेकलिस्ट और सूचनाएं एक ही जगह प्रबंधित करें।", login: "साइन इन", register: "क्रू खाता बनाएं", employee: "कर्मचारी आईडी", password: "पासवर्ड", email: "कार्य ईमेल", name: "पूरा नाम", role: "भूमिका", skill: "मुख्य कौशल", shiftStart: "शिफ्ट शुरू", shiftEnd: "शिफ्ट समाप्त", submitLogin: "सुरक्षित साइन इन", submitRegister: "अनुमोदन के लिए भेजें", pending: "खाता भेज दिया गया है। साइन इन से पहले प्रशासक की मंजूरी जरूरी है।", signedIn: "साइन इन उपयोगकर्ता", orders: "मेरे कार्य आदेश", notifications: "सूचनाएं", noOrders: "अभी कोई कार्य आदेश नहीं है।", noNotifications: "कोई सूचना नहीं।", logout: "साइन आउट", active: "सक्रिय", unread: "अपठित", refresh: "रिफ्रेश", support: "सुरक्षा हमेशा अनिवार्य है।", approval: "प्रशासक की मंजूरी लंबित", loginHint: "अपने स्वीकृत कर्मचारी आईडी और पासवर्ड का उपयोग करें।", registerHint: "कम से कम 12 अक्षरों का मजबूत पासवर्ड रखें।", checklist: "सुरक्षा चेकलिस्ट", noChecklist: "इस आदेश के लिए अभी चेकलिस्ट नहीं बनी है।", mandatory: "अनिवार्य", workerTitle: "असाइन किए गए काम की सूचनाएं", workerDescription: "आपका खाता केवल प्रशासक द्वारा भेजी गई सूचनाएं देख सकता है।", pendingTitle: "लंबित क्रू अनुमोदन", pendingDescription: "नए पंजीकरण के लिए प्रशासक की पुष्टि जरूरी है।", approve: "अनुमोदित करें", approving: "अनुमोदन हो रहा है…", dismiss: "हटाएं" },
} as const;

export default function CrewPage() {
  const [language, setLanguage] = useState<Language>("en");
  const t = copy[language];
  const [mode, setMode] = useState<"login" | "register">("login");
  const [crew, setCrew] = useState<Crew | null>(null);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [activeCrews, setActiveCrews] = useState<ActiveCrew[]>([]);
  const [assignedCrew, setAssignedCrew] = useState<Record<string, string>>({});
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [pendingCrews, setPendingCrews] = useState<PendingCrew[]>([]);
  const [checklists, setChecklists] = useState<Checklist[]>([]);
  const [checklistOrder, setChecklistOrder] = useState<string | null>(null);
  const [pendingNotice, setPendingNotice] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [approvalBusy, setApprovalBusy] = useState<string | null>(null);
  const previousPendingCount = useRef<number | null>(null);
  const [form, setForm] = useState({ employee_id: "", password: "", email: "", full_name: "", role: "GANG", primary_skill: "TRACK", shift_start: "06:00", shift_end: "14:00" });
  const isAdmin = crew?.role === "ADMIN";

  const loadWorkspace = async () => {
    try {
      const [me, notificationResponse] = await Promise.all([api.get<Crew>("/auth/me", authConfig()), api.get<Notification[]>("/notifications", authConfig())]);
      const adminData = me.data.role === "ADMIN" ? await Promise.all([api.get<WorkOrder[]>("/work-orders", authConfig()), api.get<PendingCrew[]>("/auth/pending", authConfig()), api.get<ActiveCrew[]>("/auth/active", authConfig())]) : null;
      const nextPending = adminData?.[1].data || [];
      if (previousPendingCount.current !== null && nextPending.length > previousPendingCount.current) setPendingNotice("New crew registration received. Review it below.");
      previousPendingCount.current = nextPending.length;
      setCrew(me.data); setOrders(adminData?.[0].data || []); setActiveCrews(adminData?.[2].data || []); setPendingCrews(nextPending); setNotifications(notificationResponse.data); setMessage("");
    } catch (error) {
      localStorage.removeItem(tokenKey); notifyAuthChanged(); setCrew(null); setPendingCrews([]); setOrders([]); setActiveCrews([]); setMessage(errorMessage(error));
    }
  };
  useEffect(() => { if (localStorage.getItem(tokenKey)) void loadWorkspace(); }, []);
  useEffect(() => { if (!crew) return; const timer = window.setInterval(() => void loadWorkspace(), 15000); return () => window.clearInterval(timer); }, [crew]);
  const unreadCount = useMemo(() => notifications.filter((item) => !item.read_at).length, [notifications]);
  const update = (key: string, value: string) => setForm((current) => ({ ...current, [key]: value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage("");
    try {
      if (mode === "login") {
        const result = await api.post<{ access_token: string }>("/auth/login", { employee_id: form.employee_id, password: form.password });
        localStorage.setItem(tokenKey, result.data.access_token); notifyAuthChanged(); await loadWorkspace();
      } else {
        const result = await api.post<{ email_delivery?: { status: string } }>("/auth/register", form);
        setMode("login"); setMessage(`${t.pending} ${result.data.email_delivery?.status === "QUEUED" ? "A confirmation email preview was queued." : "A confirmation email was sent."}`);
      }
    } catch (error) { setMessage(errorMessage(error)); } finally { setBusy(false); }
  };
  const logout = () => { localStorage.removeItem(tokenKey); notifyAuthChanged(); previousPendingCount.current = null; setCrew(null); setOrders([]); setActiveCrews([]); setNotifications([]); setPendingCrews([]); setChecklists([]); setChecklistOrder(null); };
  const approveCrew = async (employeeId: string) => {
    setApprovalBusy(employeeId);
    try {
      const { data } = await api.post<{ email_delivery?: { status: string } }>("/auth/approve", { employee_id: employeeId }, authConfig());
      setPendingNotice(`Approved ${employeeId}. ${data.email_delivery?.status === "QUEUED" ? "The confirmation email was queued." : "The confirmation email was sent."}`); await loadWorkspace();
    } catch (error) { setMessage(errorMessage(error)); } finally { setApprovalBusy(null); }
  };
  const openChecklist = async (order: WorkOrder) => { try { const result = await api.get<{ checklists: Checklist[] }>(`/checklists/work-order/${order.id}`, authConfig()); setChecklists(result.data.checklists); setChecklistOrder(order.id); setMessage(""); } catch (error) { setMessage(errorMessage(error)); } };
  const assignWork = async (order: WorkOrder) => { const employeeId = assignedCrew[order.id]; if (!employeeId) return; try { await api.post(`/work-orders/${order.id}/assign`, { crew_employee_id: employeeId }, authConfig()); setMessage("Work assigned. The crew member has received the plan notification."); await loadWorkspace(); } catch (error) { setMessage(errorMessage(error)); } };
  const updateChecklistItem = async (checklist: Checklist, itemId: string, value: boolean) => { try { await api.post(`/checklists/${checklist.id}/item`, { item_id: itemId, value }, authConfig()); const order = orders.find((item) => item.id === checklistOrder); if (order) await openChecklist(order); } catch (error) { setMessage(errorMessage(error)); } };

  const notificationPanel = <div className="crew-card"><div className="section-heading"><h2><Bell size={16} /> {t.notifications}</h2>{unreadCount > 0 && <span className="risk-badge risk-high">{t.unread}: {unreadCount}</span>}</div>{notifications.length === 0 ? <p className="muted crew-empty">{t.noNotifications}</p> : notifications.map((item) => <article key={item.id} className={`crew-notification ${item.read_at ? "" : "unread"}`}><strong>{item.title}</strong><p>{item.message}</p></article>)}</div>;

  return <section className="page crew-page">
    <div className="page-heading"><div><span className="eyebrow">{t.eyebrow}</span><h1>{t.title}</h1><p>{t.intro}</p></div><div className="crew-actions"><button className="language-toggle" onClick={() => setLanguage(language === "en" ? "hi" : "en")}>{language === "en" ? "हिंदी" : "English"}</button>{crew && <button className="secondary-button" onClick={logout}><LogOut size={15} />{t.logout}</button>}</div></div>
    {!crew ? <div className="crew-auth-grid"><form className="crew-card crew-form" onSubmit={submit}><div className="crew-tabs"><button type="button" className={mode === "login" ? "active" : ""} onClick={() => setMode("login")}><LogIn size={15} />{t.login}</button><button type="button" className={mode === "register" ? "active" : ""} onClick={() => setMode("register")}><UserPlus size={15} />{t.register}</button></div><p className="muted crew-hint">{mode === "login" ? t.loginHint : t.registerHint}</p><label>{t.employee}<input required value={form.employee_id} onChange={(e) => update("employee_id", e.target.value)} placeholder="EMP-001" /></label>{mode === "register" && <><label>{t.name}<input required value={form.full_name} onChange={(e) => update("full_name", e.target.value)} /></label><label>{t.email}<input required type="email" value={form.email} onChange={(e) => update("email", e.target.value)} /></label><div className="crew-field-row"><label>{t.role}<select value={form.role} onChange={(e) => update("role", e.target.value)}><option>GANG</option><option>MATE</option><option>GANGMAN</option><option>SUPERVISOR</option></select></label><label>{t.skill}<select value={form.primary_skill} onChange={(e) => update("primary_skill", e.target.value)}><option>TRACK</option><option>SIGNAL</option><option>OHE</option></select></label></div><div className="crew-field-row"><label>{t.shiftStart}<input type="time" required value={form.shift_start} onChange={(e) => update("shift_start", e.target.value)} /></label><label>{t.shiftEnd}<input type="time" required value={form.shift_end} onChange={(e) => update("shift_end", e.target.value)} /></label></div></>}<label>{t.password}<input required type="password" minLength={12} value={form.password} onChange={(e) => update("password", e.target.value)} /></label><button className="primary-button" disabled={busy}>{busy ? "…" : mode === "login" ? t.submitLogin : t.submitRegister}</button>{message && <div className="crew-message" role="alert">{message}</div>}</form><aside className="crew-card crew-safety"><UsersRound size={22} /><h2>{t.support}</h2><p>{t.approval}</p><div className="crew-safety-line"><CheckCircle2 size={16} />{language === "en" ? "Role-based access" : "भूमिका आधारित पहुंच"}</div><div className="crew-safety-line"><CheckCircle2 size={16} />{language === "en" ? "Audit-ready work orders" : "ऑडिट के लिए तैयार कार्य आदेश"}</div></aside></div> : isAdmin ? <div className="crew-workspace"><div className="crew-welcome"><div><span className="eyebrow">{t.signedIn}</span><h2>{crew.full_name}</h2><span className="muted mono">{crew.employee_id} · {crew.role} · {crew.primary_skill}</span></div><button className="secondary-button" onClick={() => void loadWorkspace()}>{t.refresh}</button></div>{pendingNotice && <div className="crew-admin-toast" role="status">{pendingNotice}<button className="text-button" onClick={() => setPendingNotice("")}>{t.dismiss}</button></div>}{pendingCrews.length > 0 && <section className="crew-card crew-pending-panel"><div className="section-heading"><div><h2>{t.pendingTitle}</h2><span className="muted text-sm">{t.pendingDescription}</span></div><span className="risk-badge risk-high">{pendingCrews.length} pending</span></div><div className="crew-pending-list">{pendingCrews.map((candidate) => <article className="crew-pending-row" key={candidate.employee_id}><div><strong>{candidate.full_name}</strong><span className="muted">{candidate.employee_id} · {candidate.email} · {candidate.role} · {candidate.primary_skill}</span></div><button className="primary-button" disabled={approvalBusy === candidate.employee_id} onClick={() => void approveCrew(candidate.employee_id)}>{approvalBusy === candidate.employee_id ? t.approving : t.approve}</button></article>)}</div></section>}<div className="crew-dashboard-grid"><div className="crew-card"><div className="section-heading"><h2>{t.orders}</h2><span className="risk-badge risk-low">{t.active}: {orders.filter((order) => order.status !== "VERIFIED").length}</span></div>{orders.length === 0 ? <p className="muted crew-empty">{t.noOrders}</p> : <div className="crew-order-list">{orders.map((order) => <article key={order.work_order_number} className="crew-order"><div><strong>{order.title}</strong><span className="muted">{order.work_order_number} · {order.section_id}</span></div><div className="crew-order-actions"><span className="risk-badge risk-medium">{order.status}</span>{order.status === "DRAFT" ? <><select aria-label={`Assign ${order.work_order_number}`} value={assignedCrew[order.id] || ""} onChange={(event) => setAssignedCrew((current) => ({ ...current, [order.id]: event.target.value }))}><option value="">Choose crew member</option>{activeCrews.filter((member) => member.primary_skill === order.required_skill || member.secondary_skills.includes(order.required_skill)).map((member) => <option key={member.employee_id} value={member.employee_id}>{member.full_name} · {member.employee_id}</option>)}</select><button type="button" className="primary-button" disabled={!assignedCrew[order.id]} onClick={() => void assignWork(order)}>Assign work</button></> : <button type="button" className="text-button" onClick={() => void openChecklist(order)}><ClipboardCheck size={13} />{t.checklist}</button>}</div></article>)}</div>}{checklistOrder && <div className="crew-checklist"><h3>{t.checklist}</h3>{checklists.length === 0 ? <p className="muted crew-empty">{t.noChecklist}</p> : checklists.map((checklist) => <div key={checklist.id} className="crew-checklist-group"><strong>{checklist.type} {checklist.is_mandatory && <span className="risk-badge risk-high">{t.mandatory}</span>}</strong>{checklist.items.map((item) => <label className="checklist-item" key={item.id}><input type="checkbox" checked={Boolean(checklist.completed_items[item.id]?.value)} disabled={Boolean(checklist.signed_at)} onChange={(event) => void updateChecklistItem(checklist, item.id, event.target.checked)} /><span>{item.text}</span></label>)}</div>)}</div>}</div>{notificationPanel}</div></div> : <div className="crew-worker-only"><div className="crew-welcome"><div><span className="eyebrow">{t.signedIn}</span><h2>{crew.full_name}</h2><span className="muted mono">{crew.employee_id} · {crew.role}</span></div><button className="secondary-button" onClick={() => void loadWorkspace()}>{t.refresh}</button></div><div className="crew-dashboard-grid worker-notifications"><div className="crew-card"><h2>{t.workerTitle}</h2><p className="muted">{t.workerDescription}</p></div>{notificationPanel}</div></div>}
  </section>;
}
