import { useState } from "react";
import { useTheme } from "../contexts/ThemeContext";

interface LoginProps {
  onGoogle: () => Promise<void>;
  onEmail: (email: string, password: string) => Promise<void>;
  onSignUp: (email: string, password: string) => Promise<void>;
  onGuest: () => Promise<void>;
}

export function Login({ onGoogle, onEmail, onSignUp, onGuest }: LoginProps) {
  const { theme, toggleTheme } = useTheme();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handle(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (err) {
      const msg =
        err instanceof Error ? err.message : "Authentication failed";
      setError(
        msg
          .replace("Firebase: ", "")
          .replace(/\(auth\/.*\)\.?/, "")
          .trim() || "Authentication failed"
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <div className="login-card">
        <div className="login-header">
          <h1>PaperTales</h1>
          <p>Research papers become illustrated stories</p>
        </div>

        <button
          className="btn-google"
          onClick={() => handle(onGoogle)}
          disabled={busy}
        >
          <svg viewBox="0 0 24 24">
            <path
              fill="#4285F4"
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
            />
            <path
              fill="#34A853"
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
            />
            <path
              fill="#FBBC05"
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18A10.96 10.96 0 0 0 1 12c0 1.77.42 3.44 1.18 4.93l3.66-2.84z"
            />
            <path
              fill="#EA4335"
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
            />
          </svg>
          Continue with Google
        </button>

        <div className="login-divider">or</div>

        <form
          className="email-form"
          onSubmit={(e) => {
            e.preventDefault();
            handle(() => onEmail(email, password));
          }}
        >
          <input
            type="email"
            placeholder="Email address"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={busy}
            autoComplete="email"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={busy}
            autoComplete="current-password"
          />
          <div className="email-actions">
            <button type="submit" className="btn-email-signin" disabled={busy}>
              Sign In
            </button>
            <button
              type="button"
              className="btn-email-signup"
              onClick={() => handle(() => onSignUp(email, password))}
              disabled={busy}
            >
              Sign Up
            </button>
          </div>
        </form>

        <div className="login-divider">or</div>

        <button
          className="btn-guest"
          onClick={() => handle(onGuest)}
          disabled={busy}
        >
          Continue as Guest
        </button>

        {error && <p className="login-error">{error}</p>}
      </div>

      <div className="theme-corner">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "light" ? "\u263E" : "\u2600"}
        </button>
      </div>
    </main>
  );
}
