import React, { useState, useEffect, useMemo } from "react";
import { useLibrary } from "../hooks/useLibrary";
import { STATUS_TABS } from "../constants";
import ItemCardGrid from "./ItemCardGrid";
import ItemTable from "./ItemTable";
import ItemDetailModal from "./ItemDetailModal";
import SeriesModal from "./SeriesModal";
import AddBookPanel from "./AddBookPanel";

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

function groupEntries(entries) {
  const seriesMap = {};
  const result = [];

  for (const entry of entries) {
    const sid = entry.item.series_id;
    if (sid) {
      if (!seriesMap[sid]) {
        seriesMap[sid] = {
          type: "series",
          id: `series-${sid}`,
          seriesId: sid,
          seriesName: entry.item.series?.name || entry.item.volume_title || "Unknown Series",
          seriesCover: entry.item.series?.cover_url || null,
          seriesData: entry.item.series || null,
          entries: [],
        };
      }
      seriesMap[sid].entries.push(entry);
    } else {
      result.push({ type: "single", id: entry.id, entry });
    }
  }

  for (const group of Object.values(seriesMap)) {
    if (group.entries.length >= 2) {
      result.push(group);
    } else {
      result.push({ type: "single", id: group.entries[0].id, entry: group.entries[0] });
    }
  }

  return result;
}

const LibraryDashboard = () => {
  const {
    viewMode, setViewMode,
    search, setSearch,
    activeStatus, setStatus,
    entries, page, setPage, totalPages, total,
    error, loading, refresh,
  } = useLibrary();

  const [selectedEntry,    setSelectedEntry]    = useState(null);
  const [selectedSeriesId, setSelectedSeriesId] = useState(null);
  const [showAddPanel,     setShowAddPanel]      = useState(false);

  const displayItems = useMemo(() => groupEntries(entries), [entries]);

  const selectedSeriesGroup = useMemo(
    () => displayItems.find((d) => d.type === "series" && d.seriesId === selectedSeriesId) || null,
    [displayItems, selectedSeriesId],
  );

  // Auto-close series modal when all its volumes are deleted
  useEffect(() => {
    if (selectedSeriesId && !loading && !selectedSeriesGroup) {
      setSelectedSeriesId(null);
    }
  }, [selectedSeriesId, selectedSeriesGroup, loading]);

  const isFiltered = search || activeStatus !== "all";

  return (
    <main className="dashboard">
      {/* Toolbar */}
      <div className="toolbar">
        <div className="toolbar-search">
          <SearchIcon />
          <input
            placeholder="Search title, author, genre…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="toolbar-spacer" />
        <div className="view-toggle">
          <button
            className={`btn-icon ${viewMode === "grid" ? "active" : ""}`}
            onClick={() => setViewMode("grid")}
            title="Grid view"
          >
            <GridIcon />
          </button>
          <button
            className={`btn-icon ${viewMode === "list" ? "active" : ""}`}
            onClick={() => setViewMode("list")}
            title="List view"
          >
            <ListIcon />
          </button>
        </div>
        <button className="btn btn-primary" onClick={() => setShowAddPanel(true)}>
          + Add book
        </button>
      </div>

      {/* Status filter tabs */}
      <div className="status-tabs">
        {STATUS_TABS.map(({ key, label }) => (
          <button
            key={key}
            className={`status-tab ${activeStatus === key ? "active" : ""}`}
            data-status={key}
            onClick={() => setStatus(key)}
          >
            {label}
          </button>
        ))}
        {total > 0 && (
          <span className="section-count">{total} {total === 1 ? "book" : "books"}</span>
        )}
      </div>

      {error && (
        <div className="alert alert-error" style={{ marginBottom: 16 }}>{error}</div>
      )}

      {/* Book list */}
      {loading ? (
        <div className="empty-state"><p>Loading…</p></div>
      ) : displayItems.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">📚</div>
          <h3>{isFiltered ? "No books found" : "Your library is empty"}</h3>
          <p>
            {isFiltered
              ? "Try a different search or filter."
              : "Add your first book to get started."}
          </p>
          {!isFiltered && (
            <button className="btn btn-primary" onClick={() => setShowAddPanel(true)}>
              + Add book
            </button>
          )}
        </div>
      ) : viewMode === "grid" ? (
        <ItemCardGrid
          displayItems={displayItems}
          onSelect={setSelectedEntry}
          onSelectSeries={(g) => setSelectedSeriesId(g.seriesId)}
        />
      ) : (
        <ItemTable
          displayItems={displayItems}
          onSelect={setSelectedEntry}
          onSelectSeries={(g) => setSelectedSeriesId(g.seriesId)}
        />
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="pagination">
          <button className="btn btn-ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            ← Prev
          </button>
          <span className="pagination-info">Page {page} of {totalPages}</span>
          <button className="btn btn-ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next →
          </button>
        </div>
      )}

      {/* Modals */}
      {showAddPanel && (
        <AddBookPanel onClose={() => setShowAddPanel(false)} onSaved={refresh} />
      )}
      {selectedSeriesGroup && (
        <SeriesModal
          seriesId={selectedSeriesGroup.seriesId}
          seriesName={selectedSeriesGroup.seriesName}
          seriesData={selectedSeriesGroup.seriesData}
          entries={selectedSeriesGroup.entries}
          onClose={() => setSelectedSeriesId(null)}
          onSelectEntry={setSelectedEntry}
          onSaved={refresh}
        />
      )}
      {selectedEntry && (
        <ItemDetailModal
          entry={selectedEntry}
          onClose={() => setSelectedEntry(null)}
          onSaved={refresh}
        />
      )}
    </main>
  );
};

export default LibraryDashboard;
