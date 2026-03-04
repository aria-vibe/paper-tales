import { Link } from "react-router-dom";
import type { User } from "firebase/auth";
import { useTheme } from "../contexts/ThemeContext";

interface AuthBarProps {
  user: User | null;
  onSignOut: () => void;
}

export function AuthBar({ user, onSignOut }: AuthBarProps) {
  const { theme, toggleTheme } = useTheme();

  return (
    <header className="auth-bar">
      <Link to="/" className="auth-logo">
        PaperTales
      </Link>
      <div className="auth-right">
        <button
          className="theme-toggle"
          onClick={toggleTheme}
          aria-label="Toggle theme"
        >
          {theme === "light" ? "\u263E" : "\u2600"}
        </button>
        {user && !user.isAnonymous && (
          <>
            <span className="user-name">
              {user.displayName || user.email || "User"}
            </span>
            <button className="btn-nav btn-nav-ghost" onClick={onSignOut}>
              Sign out
            </button>
          </>
        )}
        {user?.isAnonymous && (
          <Link to="/login">
            <button className="btn-nav btn-nav-primary">Sign In</button>
          </Link>
        )}
      </div>
    </header>
  );
}
