import { apiClient, setAuthToken } from "./client";
import {
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from "@/types";

export const authApi = {
  async login(data: LoginRequest): Promise<TokenResponse> {
    const res = await apiClient.post<TokenResponse>("/auth/login", data);
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  async register(data: RegisterRequest): Promise<User> {
    return apiClient.post<User>("/auth/register", data);
  },

  async getMe(): Promise<User> {
    return apiClient.get<User>("/auth/me");
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post("/auth/logout");
    } finally {
      setAuthToken(null);
    }
  },
};
