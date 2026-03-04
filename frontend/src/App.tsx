import { useCallback } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useAuth } from "./hooks/useAuth";
import { AuthBar } from "./components/AuthBar";
import { Home } from "./pages/Home";
import { Story } from "./pages/Story";
import "./index.css";

function App() {
  const { user, loading, signIn, signOut, getToken } = useAuth();
  const stableGetToken = useCallback(getToken, [getToken]);

  return (
    <BrowserRouter>
      <AuthBar
        user={user}
        loading={loading}
        onSignIn={signIn}
        onSignOut={signOut}
      />
      <Routes>
        <Route
          path="/"
          element={<Home user={user} getToken={stableGetToken} />}
        />
        <Route
          path="/story/:id"
          element={<Story getToken={stableGetToken} />}
        />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
