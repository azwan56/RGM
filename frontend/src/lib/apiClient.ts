import axios from "axios";
import { auth } from "./firebase";

// Create a custom axios instance
const apiClient = axios.create();

// Request interceptor to attach Firebase ID Token
apiClient.interceptors.request.use(
  async (config) => {
    // Wait for auth to initialize if it hasn't already
    await auth.authStateReady();
    
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

export default apiClient;
