import axios, { AxiosResponse } from "axios";
import type {
  User,
  UserItemData,
  Item,
  Series,
  MangaVolume,
  PagedResponse,
  LibraryParams,
  ReadingStatus,
} from "./types";

const API_BASE = process.env.REACT_APP_API_BASE ?? "http://localhost:8000";

const client = axios.create({ baseURL: API_BASE });

export const setAuthToken = (token: string | null): void => {
  if (token) {
    client.defaults.headers.common["Authorization"] = `Bearer ${token}`;
  } else {
    delete client.defaults.headers.common["Authorization"];
  }
};

export const registerUser = (payload: { username: string; password: string }): Promise<AxiosResponse<User>> =>
  client.post("/auth/register", payload, { headers: { "Content-Type": "application/json" } });

export const loginUser = (formData: URLSearchParams): Promise<AxiosResponse<{ access_token: string; token_type: string }>> =>
  client.post("/auth/token", formData, { headers: { "Content-Type": "application/x-www-form-urlencoded" } });

export const fetchMe = (): Promise<AxiosResponse<User>> => client.get("/auth/me");

export const fetchUserLibrary = (params: LibraryParams): Promise<AxiosResponse<PagedResponse<UserItemData>>> =>
  client.get("/user-items/", { params });

export const createUserEntry = (payload: { item_id?: number; item?: Partial<Item>; status?: ReadingStatus; current_page?: number }): Promise<AxiosResponse<UserItemData>> =>
  client.post("/user-items/", payload);

export const updateUserEntry = (id: number, payload: { status?: ReadingStatus; current_page?: number }): Promise<AxiosResponse<UserItemData>> =>
  client.put(`/user-items/${id}`, payload);

export const importISBN = (isbn: string): Promise<AxiosResponse> =>
  client.post("/import/isbn", { isbn });

export const fetchSeries = (): Promise<AxiosResponse<Series[]>> => client.get("/series/");

export const createSeries = (payload: Partial<Series>): Promise<AxiosResponse<Series>> =>
  client.post("/series/", payload);

export const updateSeries = (id: number, payload: Partial<Series>): Promise<AxiosResponse<Series>> =>
  client.put(`/series/${id}`, payload);

export const bulkUpdateSeriesStatus = (id: number, status: ReadingStatus): Promise<AxiosResponse<{ updated: number }>> =>
  client.patch(`/series/${id}/status`, { status });

export const deleteSeriesFromLibrary = (id: number): Promise<AxiosResponse<{ updated: number }>> =>
  client.delete(`/series/${id}/library`);

export const updateItem = (id: number, payload: Partial<Item>): Promise<AxiosResponse<Item>> =>
  client.put(`/items/${id}`, payload);

export const deleteUserEntry = (id: number): Promise<AxiosResponse<void>> =>
  client.delete(`/user-items/${id}`);

export const refreshChapters = (itemId: number): Promise<AxiosResponse<MangaVolume>> =>
  client.post(`/items/${itemId}/chapters/refresh`);
