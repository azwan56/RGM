import axios from "axios";
import { auth } from "./firebase";

// Create a custom axios instance
const apiClient = axios.create();

// Cache auth readiness — resolves once, never blocks again
let _authReady = false;
const _authReadyPromise = auth.authStateReady().then(() => { _authReady = true; });

// Request interceptor to attach Firebase ID Token
apiClient.interceptors.request.use(
  async (config) => {
    // Only wait for auth init once (first request); subsequent calls skip instantly
    if (!_authReady) {
      await _authReadyPromise;
    }

    const user = auth.currentUser;
    if (user) {
      try {
        // getIdToken() returns cached token if not expired (~instant)
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

export default apiClient;
