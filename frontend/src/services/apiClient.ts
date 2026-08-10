import { Platform } from 'react-native';
import { API_CONFIG } from '@/constants/config';

export interface AuthSession {
  authenticated: boolean;
  auth_required: boolean;
  role: 'recruiter' | 'administrator' | null;
  expires_in_seconds: number | null;
}

let unauthorizedHandler: (() => void) | null = null;
let sessionCredentialsEnabled = false;

export class ApiError extends Error {
  status: number;
  data: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_CONFIG.BASE_URL}${endpoint}`;
  
  const defaultHeaders: Record<string, string> = {
    'Accept': 'application/json',
  };

  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.TIMEOUT_MS);

  try {
    const response = await fetch(url, {
      ...options,
      credentials: options.credentials ?? (sessionCredentialsEnabled ? 'include' : 'omit'),
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    let data: any;
    const contentType = response.headers.get('content-type');
    if (contentType && contentType.includes('application/json')) {
      data = await response.json();
    } else {
      data = await response.text();
    }

    if (!response.ok) {
      if (response.status === 401 && endpoint !== '/api/auth/session') {
        unauthorizedHandler?.();
      }
      const errorMessage =
        (typeof data === 'object' && data?.detail) ||
        (typeof data === 'string' && data) ||
        `HTTP Error ${response.status}`;
      throw new ApiError(errorMessage, response.status, data);
    }

    return data as T;
  } catch (error: any) {
    clearTimeout(timeoutId);
    if (error.name === 'AbortError') {
      throw new ApiError('Request timed out', 408);
    }
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(error.message || 'Network request failed', 0);
  }
}

export const apiClient = {
  setUnauthorizedHandler: (handler: (() => void) | null) => {
    unauthorizedHandler = handler;
  },

  getSession: async () => {
    const publicStatus = await request<AuthSession>('/api/auth/session', {
      method: 'GET',
      credentials: 'omit',
    });
    sessionCredentialsEnabled = publicStatus.auth_required;
    if (!publicStatus.auth_required) {
      return publicStatus;
    }
    return request<AuthSession>('/api/auth/session', {
      method: 'GET',
      credentials: 'include',
    });
  },

  createSession: (apiKey: string) => {
    sessionCredentialsEnabled = true;
    return request<AuthSession>('/api/auth/session', {
      method: 'POST',
      headers: { 'X-API-Key': apiKey },
      credentials: 'include',
    });
  },

  deleteSession: () => request<AuthSession>('/api/auth/session', {
    method: 'DELETE',
    credentials: 'include',
  }),

  get: <T>(endpoint: string, headers?: Record<string, string>) =>
    request<T>(endpoint, { method: 'GET', headers }),

  post: <T>(endpoint: string, body?: any, headers?: Record<string, string>) =>
    request<T>(endpoint, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
      headers,
    }),

  put: <T>(endpoint: string, body?: any, headers?: Record<string, string>) =>
    request<T>(endpoint, {
      method: 'PUT',
      body: body instanceof FormData ? body : JSON.stringify(body),
      headers,
    }),

  delete: <T>(endpoint: string, headers?: Record<string, string>) =>
    request<T>(endpoint, { method: 'DELETE', headers }),

  uploadFile: <T>(
    endpoint: string,
    file: { uri: string; name: string; type: string; rawFile?: any },
    additionalFields?: Record<string, string>
  ) => {
    const formData = new FormData();

    if (Platform.OS === 'web') {
      if (file.rawFile instanceof File || file.rawFile instanceof Blob) {
        formData.append('file', file.rawFile, file.name);
      } else {
        throw new ApiError('No valid file object provided for upload. Please re-select the resume file.', 400);
      }
    } else {
      formData.append('file', {
        uri: file.uri,
        name: file.name,
        type: file.type || 'application/octet-stream',
      } as any);
    }

    if (additionalFields) {
      Object.entries(additionalFields).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          formData.append(key, value);
        }
      });
    }

    return request<T>(endpoint, {
      method: 'POST',
      body: formData,
    });
  },
};
