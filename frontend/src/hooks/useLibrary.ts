import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchUserLibrary } from "../api";
import type { UserItemData, ReadingStatus } from "../types";

interface LibraryState {
  viewMode: string;
  setViewMode: (mode: string) => void;
  search: string;
  setSearch: (value: string) => void;
  activeStatus: string;
  setStatus: (key: string) => void;
  entries: UserItemData[];
  page: number;
  setPage: React.Dispatch<React.SetStateAction<number>>;
  totalPages: number;
  total: number;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

export function useLibrary(): LibraryState {
  const [viewMode, setViewMode] = useState<string>("grid");
  const [search, setSearchState] = useState<string>("");
  const [activeStatus, setStatusState] = useState<string>("all");
  const [page, setPage] = useState<number>(1);

  const queryClient = useQueryClient();

  const queryKey = ["library", { search, activeStatus, page }] as const;

  const { data, isLoading, error } = useQuery({
    queryKey,
    queryFn: () => {
      const params: Record<string, string | number> = {
        page,
        page_size: 100,
        sort_by: "title",
        sort_dir: "asc",
      };
      if (search) params.q = search;
      if (activeStatus !== "all") params.status = activeStatus as ReadingStatus;
      return fetchUserLibrary(params).then((res) => res.data);
    },
    staleTime: 30_000,
  });

  const setSearch = (value: string): void => {
    setSearchState(value);
    setPage(1);
  };

  const setStatus = (key: string): void => {
    setStatusState(key);
    setPage(1);
  };

  const refresh = (): void => {
    queryClient.invalidateQueries({ queryKey: ["library"] });
  };

  const axiosError = error as { response?: { data?: { detail?: string } } } | null;
  const errorMessage = axiosError?.response?.data?.detail ?? (error ? "Unable to load library" : null);

  return {
    viewMode,
    setViewMode,
    search,
    setSearch,
    activeStatus,
    setStatus,
    entries: data?.items ?? [],
    page,
    setPage,
    totalPages: data?.pages ?? 1,
    total: data?.total ?? 0,
    error: errorMessage,
    loading: isLoading,
    refresh,
  };
}
