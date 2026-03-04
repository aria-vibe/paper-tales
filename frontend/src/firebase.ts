import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyDmHdqXqOWRkg7Ua4c586jjfVLcazTQQ4Y",
  authDomain: "gen-lang-client-0383770485.firebaseapp.com",
  projectId: "gen-lang-client-0383770485",
  storageBucket: "gen-lang-client-0383770485.firebasestorage.app",
  messagingSenderId: "197966500173",
  appId: "1:197966500173:web:616d5aeaa897a7c39d6704",
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
