import axios from "axios";

const API_BASE = process.env.REACT_APP_API_BASE || "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

export const setAuthToken = (token) => {
  if (token) {
    client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete client.defaults.headers.common["Authorization"];
  }
};

export const registerUser = (payload) =>
  client.post("/auth/register", payload, { headers: { "Content-Type": "application/json" } });

export const loginUser = (formData) =>
  client.post("/auth/token", formData, { headers: { "Content-Type": "application/x-www-form-urlencoded" } });

export const fetchMe = () => client.get("/auth/me");

export const fetchUserLibrary = (params) => client.get("/user-items/", { params });
export const createUserEntry = (payload) => client.post("/user-items/", payload);
export const updateUserEntry = (id, payload) => client.put(`/user-items/${id}`, payload);

export const importISBN = (isbn) => client.post("/import/isbn", { isbn });

export const fetchSeries = () => client.get("/series/");
export const createSeries = (payload) => client.post("/series/", payload);

export const updateItem = (id, payload) => client.put(`/items/${id}`, payload);
