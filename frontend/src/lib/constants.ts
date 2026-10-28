import { browser } from '$app/environment';

export function api() {
  if (browser) {
    return window.location.origin;
  }
  return process.env.API_URL || 'http://localhost:8000';
}

export const API = api();
