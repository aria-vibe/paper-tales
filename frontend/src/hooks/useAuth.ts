import { useEffect, useState } from "react";
import {
  onAuthStateChanged,
  signInWithPopup,
  signOut as fbSignOut,
  type User,
} from "firebase/auth";
import { auth, googleProvider } from "../firebase";

export function useAuth() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (u) => {
      setUser(u);
      setLoading(false);
    });
    return unsubscribe;
  }, []);

  async function signIn() {
    await signInWithPopup(auth, googleProvider);
  }

  async function signOut() {
    await fbSignOut(auth);
  }

  async function getToken(): Promise<string> {
    if (!user) throw new Error("Not signed in");
    return user.getIdToken();
  }

  return { user, loading, signIn, signOut, getToken };
}
