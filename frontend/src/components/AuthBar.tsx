import { useState } from "react";
import { Link } from "react-router-dom";
import type { User } from "firebase/auth";
import { useTheme } from "../contexts/ThemeContext";
import { MyStories } from "./MyStories";

interface AuthBarProps {
  user: User | null;
  onSignOut: () => void;
  getToken?: () => Promise<string>;
  onUpgradeFromGuest?: () => void;
}

export function AuthBar({ user, onSignOut, getToken, onUpgradeFromGuest }: AuthBarProps) {
  const { theme, toggleTheme } = useTheme();
  const [drawerOpen, setDrawerOpen] = useState(false);

  return (
    <>
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
              <button
                className="btn-nav btn-nav-ghost"
                onClick={() => setDrawerOpen(true)}
              >
                My Stories
              </button>
              <span className="user-name">
                {user.displayName || user.email || "User"}
              </span>
              <button className="btn-nav btn-nav-ghost" onClick={onSignOut}>
                Sign out
              </button>
            </>
          )}
          {user?.isAnonymous && (
            <button
              className="btn-nav btn-nav-primary"
              onClick={onUpgradeFromGuest}
            >
              Sign In
            </button>
          )}
        </div>
      </header>
      {getToken && (
        <MyStories
          open={drawerOpen}
          onClose={() => setDrawerOpen(false)}
          getToken={getToken}
        />
      )}
    </>
  );
}
