import { apiClient, unwrap } from "./client";
import { ApiError } from "./errors";
import type { components } from "./schema.gen";

export type User = components["schemas"]["UserResponse"];
export type LoginInput = components["schemas"]["LoginRequest"];
export type RegisterInput = components["schemas"]["RegisterRequest"];

export function isOrganizer(user: User): boolean {
  return user.role === "organizer";
}

export async function logIn(input: LoginInput): Promise<User> {
  return unwrap(await apiClient.POST("/api/auth/login", { body: input }));
}

export async function register(input: RegisterInput): Promise<User> {
  return unwrap(await apiClient.POST("/api/auth/register", { body: input }));
}

export async function logOut(): Promise<void> {
  unwrap(await apiClient.POST("/api/auth/logout"));
}

/** Текущий пользователь или `null`, если сессии нет: для SPA это обычное состояние, не сбой. */
export async function fetchCurrentUser(): Promise<User | null> {
  try {
    return unwrap(await apiClient.GET("/api/auth/me"));
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}
