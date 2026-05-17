export const TOKEN_KEY = "bookspace_access_token";

export const saveToken = (token: string): void => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  }
};

export const getToken = (): string | null => localStorage.getItem(TOKEN_KEY);

export const clearToken = (): void => localStorage.removeItem(TOKEN_KEY);
