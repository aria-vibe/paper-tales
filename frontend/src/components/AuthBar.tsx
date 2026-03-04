import type { User } from "firebase/auth";

interface AuthBarProps {
  user: User | null;
  loading: boolean;
  onSignIn: () => void;
  onSignOut: () => void;
}

export function AuthBar({ user, loading, onSignIn, onSignOut }: AuthBarProps) {
  if (loading) return null;

  return (
    <header className="auth-bar">
      {user ? (
        <>
          <span className="auth-user">{user.displayName}</span>
          <button onClick={onSignOut} className="btn-link">
            Sign out
          </button>
        </>
      ) : (
        <button onClick={onSignIn} className="btn-primary">
          Sign in with Google
        </button>
      )}
    </header>
  );
}
