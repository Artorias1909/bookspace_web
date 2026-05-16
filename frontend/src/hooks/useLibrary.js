import { useState, useEffect, useCallback } from "react";
import { fetchUserLibrary } from "../api";

/**
 * Manages all state and data-fetching for the library dashboard.
 * Encapsulates pagination, search, status filtering, and sort.
 */
export function useLibrary() {
  const [viewMode,     setViewMode]     = useState("grid");
  const [search,       setSearchState]  = useState("");
  const [activeStatus, setStatusState]  = useState("all");
  const [entries,      setEntries]      = useState([]);
  const [page,         setPage]         = useState(1);
  const [totalPages,   setTotalPages]   = useState(1);
  const [total,        setTotal]        = useState(0);
  const [error,        setError]        = useState(null);
  const [loading,      setLoading]      = useState(false);
  const [refreshTick,  setRefreshTick]  = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = { page, page_size: 100, sort_by: "title", sort_dir: "asc" };
      if (search) params.q = search;
      if (activeStatus !== "all") params.status = activeStatus;
      const res = await fetchUserLibrary(params);
      setEntries(res.data.items);
      setTotalPages(res.data.pages);
      setTotal(res.data.total);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to load library");
    } finally {
      setLoading(false);
    }
  }, [search, page, activeStatus, refreshTick]); // eslint-disable-line

  useEffect(() => { load(); }, [load]);

  const setSearch = (value) => {
    setSearchState(value);
    setPage(1);
  };

  const setStatus = (key) => {
    setStatusState(key);
    setPage(1);
  };

  const refresh = () => setRefreshTick((t) => !t);

  return {
    viewMode, setViewMode,
    search, setSearch,
    activeStatus, setStatus,
    entries,
    page, setPage,
    totalPages,
    total,
    error,
    loading,
    refresh,
  };
}
