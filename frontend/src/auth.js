export const TOKEN_KEY = "bookspace_access_token";

export const saveToken = (token) => {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  }
};

export const getToken = () => localStorage.getItem(TOKEN_KEY);

export const clearToken = () => localStorage.removeItem(TOKEN_KEY);
