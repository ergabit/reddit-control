import { kit } from '$app/environment';

export function api() {
  if (kit.serverLoaded) {
    return '';
  }
  return import.meta.env.VITE_API_URL || 'http://localhost:8000';
}
