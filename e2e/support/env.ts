export const APP_URL = process.env.E2E_APP_URL ?? "http://127.0.0.1:8000";
export const MAILPIT_URL = process.env.E2E_MAILPIT_URL ?? "http://127.0.0.1:8025";
// Значения-заглушки из `.env.example` (dev only).
export const ORGANIZER_EMAIL = process.env.ORGANIZER_EMAIL ?? "organizer@example.com";
export const ORGANIZER_PASSWORD = process.env.ORGANIZER_PASSWORD ?? "dev-only-change-me-organizer";
export const PASSWORD = "e2e-password-123";
