import { Clock3, MailCheck } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
export default function PendingApprovalPage() {
  const id = (useLocation().state as { employeeId?: string } | null)?.employeeId;
  return <main className="approval-wait"><div className="wait-icon"><Clock3 size={30} /></div><span className="eyebrow">ACCOUNT CREATED</span><h1>Administrator approval pending</h1><p>{id ? <><b>{id}</b> was registered successfully. </> : null}Your account must be approved before you can sign in.</p><div className="wait-step"><MailCheck size={20} /><span><b>What happens next?</b><small>The administrator receives an approval request. You will receive confirmation after verification.</small></span></div><Link className="primary" to="/login">Return to sign in</Link></main>;
}
