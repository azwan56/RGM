import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth } from "firebase/auth";

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID
};

// Initialize Firebase
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();
const auth = getAuth(app);

// Lazy-loaded modules — only imported when actually used (saves ~150KB from initial bundle)
let _db: any = null;
let _storage: any = null;

function getDb() {
  if (!_db) {
    const { getFirestore, setLogLevel } = require("firebase/firestore");
    setLogLevel("silent");
    _db = getFirestore(app, "gentrain");
  }
  return _db;
}

function getStorageInstance() {
  if (!_storage) {
    const { getStorage } = require("firebase/storage");
    _storage = getStorage(app);
  }
  return _storage;
}

// Export auth directly (always needed), db/storage as lazy getters
const db = new Proxy({} as any, { get: (_t, prop) => getDb()[prop] });
const storage = new Proxy({} as any, { get: (_t, prop) => getStorageInstance()[prop] });

export { app, auth, db, storage };
