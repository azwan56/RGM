import axios from "axios";
import { auth } from "./firebase";

const backendUrl = process.env.EXPO_PUBLIC_BACKEND_URL || "http://localhost:8000";

const apiClient = axios.create({
  baseURL: backendUrl,
});

let _authReady = false;
const _authReadyPromise = auth.authStateReady().then(() => {
  _authReady = true;
});

apiClient.interceptors.request.use(
  async (config) => {
    if (!_authReady) {
      await _authReadyPromise;
    }

    const user = auth.currentUser;
    if (user) {
      try {
        const token = await user.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
      } catch (error) {
        console.error("Failed to get Firebase token:", error);
      }
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

export { apiClient, backendUrl };
