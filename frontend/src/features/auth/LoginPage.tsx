import { Mail } from "lucide-react";
import { FormEvent, useMemo, useState } from "react";

import Button from "../../components/ui/Button";
import { useAuth } from "./AuthContext";

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

export default function LoginPage() {
  const { signInWithGoogle, signInWithMagicLink } = useAuth();
  const [email, setEmail] = useState("");
  const [isSending, setIsSending] = useState(false);

  const canSubmit = useMemo(() => isValidEmail(email), [email]);

  async function handleMagicLinkSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }
    setIsSending(true);
    try {
      await signInWithMagicLink(email);
    } finally {
      setIsSending(false);
    }
  }

  return (
    <section className="login-page page-section" aria-labelledby="login-title">
      <div className="login-copy">
        <p className="eyebrow">Authentication</p>
        <h1 id="login-title">Sign in</h1>
        <p>
          Use Google OAuth or a magic link. Portfolius stores portfolio data
          against your Supabase user ID.
        </p>
      </div>

      <div className="login-panel">
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
      </div>
    </section>
  );
}
