import React, { useEffect, useState, useCallback } from "react";
import { fetchUserLibrary } from "../api";
import ItemCardGrid from "./ItemCardGrid";
import ItemTable from "./ItemTable";
import ItemDetailModal from "./ItemDetailModal";
import AddBookPanel from "./AddBookPanel";

const STATUS_TABS = [
  { key: "all",       label: "All" },
  { key: "reading",   label: "Reading" },
  { key: "unread",    label: "Unread" },
  { key: "completed", label: "Completed" },
  { key: "owned",     label: "Owned" },
  { key: "wishlist",  label: "Wishlist" },
];

const SearchIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
  </svg>
);

const GridIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/>
    <rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/>
  </svg>
);

const ListIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
    <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/>
    <line x1="8" y1="18" x2="21" y2="18"/>
    <line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/>
    <line x1="3" y1="18" x2="3.01" y2="18"/>
  </svg>
);

const LibraryDashboard = () => {
  const [viewMode, setViewMode] = useState("grid");
  const [search, setSearch] = useState("");
  const [activeStatus, setActiveStatus] = useState("all");
  const [entries, setEntries] = useState([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedEntry, setSelectedEntry] = useState(null);
  const [showAddPanel, setShowAddPanel] = useState(false);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [refresh, setRefresh] = useState(false);

  const loadEntries = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const params = { page, page_size: 30, sort_by: "title", sort_dir: "asc" };
      if (search) params.q = search;
      if (activeStatus !== "all") params.status = activeStatus;
      const response = await fetchUserLibrary(params);
      setEntries(response.data.items);
      setTotalPages(response.data.pages);
      setTotal(response.data.total);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to load library");
    } finally {
      setLoading(false);
    }
  }, [search, page, activeStatus, refresh]);

  useEffect(() => { loadEntries(); }, [loadEntries]);

  const handleStatusTab = (key) => {
    setActiveStatus(key);
    setPage(1);
  };

  const handleSearch = (e) => {
    setSearch(e.target.value);
    setPage(1);
  };

  const triggerRefresh = () => setRefresh((p) => !p);

  return (
    <main className="dashboard">
      {/* Toolbar */}
      <div className="toolbar">
        <div className="toolbar-search">
          <SearchIcon />
          <input
            placeholder="Search title, author, genre…"
            value={search}
            onChange={handleSearch}
          />
        </div>
        <div className="toolbar-spacer" />
        <div className="view-toggle">
          <button className={`btn-icon ${viewMode === "grid" ? "active" : ""}`} onClick={() => setViewMode("grid")} title="Grid view">
            <GridIcon />
          </button>
          <button className={`btn-icon ${viewMode === "list" ? "active" : ""}`} onClick={() => setViewMode("list")} title="List view">
            <ListIcon />
          </button>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddPanel(true)}>
          + Add book
        </button>
      </div>

      {/* Status filter */}
      <div className="status-tabs">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`status-tab ${activeStatus === key ? "active" : ""}`}
            data-status={key}
            onClick={() => handleStatusTab(key)}
          >
            {label}
          </button>
        ))}
        {total > 0 && (
          <span className="section-count">{total} {total === 1 ? "book" : "books"}</span>
        )}
      </div>

      {error && <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>}

      {/* Book list */}
      {loading ? (
        <div className="empty-state"><p>Loading…</p></div>
      ) : entries.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📚</div>
          <h3>{search || activeStatus !== "all" ? "No books found" : "Your library is empty"}</h3>
          <p>{search || activeStatus !== "all" ? "Try a different search or filter." : "Add your first book to get started."}</p>
          {!search && activeStatus === "all" && (
            <button className="btn btn-primary" onClick={() => setShowAddPanel(true)}>+ Add book</button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <ItemCardGrid entries={entries} onSelect={setSelectedEntry} />
      ) : (
        <ItemTable entries={entries} onSelect={setSelectedEntry} />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>← Prev</button>
          <span className="pagination-info">Page {page} of {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next →</button>
        </div>
      )}

      {/* Modals */}
      {showAddPanel && (
        <AddBookPanel onClose={() => setShowAddPanel(false)} onSaved={triggerRefresh} />
      )}
      {selectedEntry && (
        <ItemDetailModal entry={selectedEntry} onClose={() => setSelectedEntry(null)} onSaved={triggerRefresh} />
      )}
    </main>
  );
};

export default LibraryDashboard;
