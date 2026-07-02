import { Mail } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useAuth } from "./AuthContext";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

// Decorative ledger lines for the hero — illustrative, not live data.
const ledgerRows = [
  { label: "US large cap", value: "38.0%" },
  { label: "International", value: "24.1%" },
  { label: "Technology", value: "17.5%" },
  { label: "Healthcare", value: "11.9%" },
  { label: "Cash & other", value: "8.5%" },
];

export default function LoginPage() {
  const { signInWithGoogle, signInWithMagicLink } = useAuth();
  const [email, setEmail] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  const canSubmit = useMemo(() => isValidEmail(email), [email]);

  async function handleMagicLinkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSending(true);
    setSendError(null);
    try {
      await signInWithMagicLink(email);
    } catch {
      setSendError("Could not send magic link. Check your email address and try again.");
    } finally {
      setIsSending(false);
    }
  }

  return (
    <main className="login-screen">
      <div className="login-layout">
      <section className="login-hero" aria-labelledby="login-title">
        <div className="wordmark wordmark--login">portfolius<span /></div>
        <p className="eyebrow">Private portfolio ledger</p>
        <h1 id="login-title">Every position, on one quiet page.</h1>
        <p className="login-lede">
          Holdings, allocation, and what-if trades across markets and
          currencies — kept like a ledger, read at a glance.
        </p>
        <dl className="login-ledger" aria-hidden="true">
          {ledgerRows.map((row) => (
            <div key={row.label}>
              <dt>{row.label}</dt>
              <dd className="num">{row.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="login-panel" aria-labelledby="login-panel-title">
        <h2 id="login-panel-title">Sign in</h2>
        <Button className="login-google-button" onClick={signInWithGoogle}>
          Continue with Google
        </Button>

        <form className="magic-link-form" onSubmit={handleMagicLinkSubmit}>
          <label htmlFor="magic-link-email">Email address</label>
          <input
            id="magic-link-email"
            name="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            type="email"
            value={email}
          />
          {sendError ? (
            <p className="form-error" role="alert">{sendError}</p>
          ) : null}
          <Button
            disabled={!canSubmit}
            icon={Mail}
            loading={isSending}
            type="submit"
            variant="secondary"
          >
            Send magic link
          </Button>
        </form>
        <p className="login-footnote">
          The magic link signs you in from your inbox — no password needed.
        </p>
      </section>
      </div>
    </main>
  );
}
