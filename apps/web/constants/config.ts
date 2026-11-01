export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export const POLL_MS = 4000;
export const SESSION_TOKEN_KEY = "culpa.session";
export const SESSION_USER_KEY = "culpa.sessionUser";
export const BUYER_ID_KEY = "culpa.buyerId";
export const DEVICE_ID_KEY = "culpa.deviceId";
