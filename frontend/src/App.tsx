import { useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { AuthBar } from "./components/AuthBar";
import { Login } from "./pages/Login";
import { Home } from "./pages/Home";
import { Story } from "./pages/Story";

function App() {
  const {
    user,
    loading,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    signInAsGuest,
    signOut,
    getToken,
  } = useAuth();
  const stableGetToken = useCallback(getToken, [getToken]);

  if (loading) return null;

  return (
    <BrowserRouter>
      {user ? (
        <>
          <AuthBar user={user} onSignOut={signOut} getToken={stableGetToken} onUpgradeFromGuest={signOut} />
          <Routes>
            <Route
              path="/"
              element={<Home user={user} getToken={stableGetToken} />}
            />
            <Route
              path="/story/:id"
              element={<Story getToken={stableGetToken} />}
            />
            <Route
              path="/login"
              element={<Navigate to="/" replace />}
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </>
      ) : (
        <Routes>
          <Route
            path="*"
            element={
              <Login
                onGoogle={signInWithGoogle}
                onEmail={signInWithEmail}
                onSignUp={signUpWithEmail}
                onGuest={signInAsGuest}
              />
            }
          />
        </Routes>
      )}
    </BrowserRouter>
  );
}

export default App;
