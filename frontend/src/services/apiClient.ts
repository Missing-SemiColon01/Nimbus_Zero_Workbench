import { backendUrl } from './backendConfig';
import { authService } from './authService';

/**
 * Backend-ready authenticated API helper.
 * Automatically attaches Authorization header if JWT token is stored,
 * and handles FormData vs JSON content types cleanly.
 */
export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = authService.getToken();
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData;

  const headers: Record<string, string> = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(backendUrl(path), {
    ...options,
    headers,
  });

  if (!response.ok) {
    if (response.status === 401) {
      // Token expired or invalid
      authService.removeToken();
    }
    const errorText = await response.text().catch(() => 'Request failed');
    let message = errorText;
    try {
      const json = JSON.parse(errorText);
      message = json.detail || json.message || errorText;
    } catch {
      // keep raw message
    }
    throw new Error(message || `Request failed with status ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
