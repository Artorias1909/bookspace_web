import React, { useState } from "react";
import { bulkUpdateSeriesStatus, updateSeries, deleteSeriesFromLibrary } from "../api";

const STATUS_OPTIONS = [
  { value: "unread",    label: "Ungelesen" },
  { value: "reading",   label: "Am Lesen" },
  { value: "completed", label: "Abgeschlossen" },
  { value: "owned",     label: "Besitze ich" },
  { value: "wishlist",  label: "Wunschliste" },
];

const VolumeRow = ({ entry, onSelectEntry, indent = false }) => (
  <li
    className="series-volume-row"
    style={indent ? { paddingLeft: 24 } : undefined}
    onClick={() => onSelectEntry(entry)}
  >
    <div className="series-volume-cover">
      {entry.item.cover_url
        ? <img src={entry.item.cover_url} alt={entry.item.title} />
        : <div className="series-volume-cover-placeholder">📖</div>
      }
    </div>
    <div className="series-volume-info">
      <span className="series-volume-title">
        {entry.item.volume_number
          ? `Band ${entry.item.volume_number}`
          : entry.item.title}
      </span>
      {entry.item.volume_title && entry.item.volume_title !== entry.item.title && (
        <span className="series-volume-subtitle">{entry.item.volume_title}</span>
      )}
    </div>
    <span className={`status-badge ${entry.status}`} style={{ marginLeft: "auto", flexShrink: 0 }}>
      {entry.status}
    </span>
    {entry.item.page_count > 0 && (
      <div className="series-volume-progress">
        <div className="progress-bar-wrap" style={{ width: 60 }}>
          <div className="progress-bar" style={{ width: `${entry.progress_percent}%` }} />
        </div>
      </div>
    )}
  </li>
);

const SeriesModal = ({ seriesId, seriesName, seriesData, entries, onClose, onSelectEntry, onSaved }) => {
  const [bulkStatus, setBulkStatus]     = useState("");
  const [bulkLoading, setBulkLoading]   = useState(false);
  const [bulkError, setBulkError]       = useState(null);

  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [editingCover, setEditingCover] = useState(false);
  const [coverInput, setCoverInput]     = useState(seriesData?.cover_url || "");
  const [coverLoading, setCoverLoading] = useState(false);
  const [coverError, setCoverError]     = useState(null);

  const sorted = [...entries].sort((a, b) => {
    const av = parseFloat(a.item.volume_number) || 0;
    const bv = parseFloat(b.item.volume_number) || 0;
    return av - bv;
  });

  // Group by box_set_id: { boxSetId -> { box, entries[] } } plus standalone entries
  const boxSetGroups = {};
  const standaloneEntries = [];
  for (const entry of sorted) {
    const bs = entry.item.box_set;
    if (bs) {
      if (!boxSetGroups[bs.id]) boxSetGroups[bs.id] = { box: bs, entries: [] };
      boxSetGroups[bs.id].entries.push(entry);
    } else {
      standaloneEntries.push(entry);
    }
  }
  const hasBoxSets = Object.keys(boxSetGroups).length > 0;

  const handleBulkStatus = async (status) => {
    if (!status) return;
    setBulkLoading(true);
    setBulkError(null);
    try {
      await bulkUpdateSeriesStatus(seriesId, status);
      onSaved();
      onClose();
    } catch {
      setBulkError("Status konnte nicht gesetzt werden.");
      setBulkLoading(false);
    }
  };

  const handleDeleteSeries = async () => {
    setDeleteLoading(true);
    try {
      await deleteSeriesFromLibrary(seriesId);
      onSaved();
      onClose();
    } catch {
      setDeleteLoading(false);
      setDeleteConfirm(false);
    }
  };

  const handleCoverSave = async () => {
    if (!seriesData) return;
    setCoverLoading(true);
    setCoverError(null);
    try {
      await updateSeries(seriesId, {
        name: seriesData.name,
        type: seriesData.type,
        total_volumes: seriesData.total_volumes ?? null,
        cover_url: coverInput || null,
      });
      onSaved();
      setEditingCover(false);
    } catch {
      setCoverError("Coverbild konnte nicht gespeichert werden.");
    } finally {
      setCoverLoading(false);
    }
  };

  const currentCover = seriesData?.cover_url
    || entries.find((e) => e.item.cover_url)?.item.cover_url
    || null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 540 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ fontSize: "1rem" }}>{seriesName}</h2>
          <span style={{ color: "var(--text-3)", fontSize: "0.85rem", marginLeft: 8 }}>
            {entries.length} {entries.length === 1 ? "Band" : "Bände"}
          </span>
          <button className="btn btn-ghost" style={{ padding: "6px 12px", marginLeft: "auto" }} onClick={onClose}>✕</button>
        </div>

        {/* Series cover editor */}
        <div style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div
            style={{ width: 64, height: 88, flexShrink: 0, borderRadius: 4, overflow: "hidden", background: "var(--surface-2)", cursor: "pointer", position: "relative" }}
            onClick={() => setEditingCover(!editingCover)}
            title="Coverbild ändern"
          >
            {currentCover
              ? <img src={currentCover} alt={seriesName} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
              : <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.5rem" }}>📚</div>
            }
            <div style={{
              position: "absolute", inset: 0, background: "rgba(0,0,0,0.45)",
              display: "flex", alignItems: "center", justifyContent: "center",
              opacity: editingCover ? 1 : 0, transition: "opacity 0.15s",
              fontSize: "0.65rem", color: "#fff", textAlign: "center", padding: 4,
            }}>
              ✏️ Ändern
            </div>
          </div>

          <div style={{ flex: 1 }}>
            {editingCover ? (
              <>
                <p style={{ fontSize: "0.8rem", color: "var(--text-2)", margin: "0 0 6px" }}>
                  Bild-URL für die Reihe (leer lassen = automatisch vom ersten Band)
                </p>
                <div style={{ display: "flex", gap: 6 }}>
                  <input
                    className="input"
                    style={{ flex: 1, fontSize: "0.85rem" }}
                    placeholder="https://..."
                    value={coverInput}
                    onChange={(e) => setCoverInput(e.target.value)}
                  />
                  <button className="btn btn-primary" style={{ padding: "6px 12px", fontSize: "0.85rem" }} onClick={handleCoverSave} disabled={coverLoading}>
                    {coverLoading ? "…" : "OK"}
                  </button>
                  <button className="btn btn-ghost" style={{ padding: "6px 10px", fontSize: "0.85rem" }} onClick={() => setEditingCover(false)}>
                    ✕
                  </button>
                </div>
                {/* Quick-select from volume covers */}
                {entries.some((e) => e.item.cover_url) && (
                  <div style={{ marginTop: 8, display: "flex", gap: 6, flexWrap: "wrap" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-3)", alignSelf: "center" }}>
                      Oder Bandcover übernehmen:
                    </span>
                    {entries.filter((e) => e.item.cover_url).map((e) => (
                      <img
                        key={e.id}
                        src={e.item.cover_url}
                        alt={e.item.title}
                        title={`Band ${e.item.volume_number || e.item.title}`}
                        style={{ width: 32, height: 44, objectFit: "cover", borderRadius: 3, cursor: "pointer", border: coverInput === e.item.cover_url ? "2px solid var(--accent)" : "2px solid transparent" }}
                        onClick={() => setCoverInput(e.item.cover_url)}
                      />
                    ))}
                  </div>
                )}
                {coverError && <p style={{ color: "var(--error)", fontSize: "0.8rem", margin: "4px 0 0" }}>{coverError}</p>}
              </>
            ) : (
              <div style={{ fontSize: "0.85rem", color: "var(--text-2)" }}>
                <strong style={{ color: "var(--text-1)" }}>{seriesName}</strong>
                <br />
                <span style={{ fontSize: "0.8rem", color: "var(--text-3)" }}>
                  {seriesData?.type === "manga" ? "Manga" : seriesData?.type === "comic" ? "Comic" : "Buch"}
                  {seriesData?.total_volumes ? ` · ${seriesData.total_volumes} Bände gesamt` : ""}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Volume list */}
        <div className="modal-body" style={{ padding: 0 }}>
          <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {hasBoxSets ? (
              <>
                {Object.values(boxSetGroups).map(({ box, entries: bsEntries }) => (
                  <li key={`bs-${box.id}`}>
                    <div style={{
                      padding: "6px 16px", fontSize: "0.78rem", fontWeight: 600,
                      color: "var(--accent)", background: "var(--surface-2)",
                      borderTop: "1px solid var(--border)", borderBottom: "1px solid var(--border)",
                    }}>
                      📦 {box.name || `Sammelbox Bände ${box.volume_from}–${box.volume_to}`}
                      <span style={{ fontWeight: 400, color: "var(--text-3)", marginLeft: 8 }}>
                        Band {box.volume_from}–{box.volume_to}
                      </span>
                    </div>
                    <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
                      {bsEntries.map((entry) => (
                        <VolumeRow key={entry.id} entry={entry} onSelectEntry={onSelectEntry} indent />
                      ))}
                    </ul>
                  </li>
                ))}
                {standaloneEntries.length > 0 && standaloneEntries.map((entry) => (
                  <VolumeRow key={entry.id} entry={entry} onSelectEntry={onSelectEntry} />
                ))}
              </>
            ) : (
              sorted.map((entry) => (
                <VolumeRow key={entry.id} entry={entry} onSelectEntry={onSelectEntry} />
              ))
            )}
          </ul>
        </div>

        {/* Footer: bulk status */}
        <div className="modal-footer" style={{ gap: 8, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1 }}>
            <label style={{ fontSize: "0.85rem", color: "var(--text-2)", whiteSpace: "nowrap" }}>
              Alle markieren als:
            </label>
            <select
              className="input"
              style={{ flex: 1, fontSize: "0.85rem" }}
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
              disabled={bulkLoading}
            >
              <option value="">— Status wählen —</option>
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <button
              className="btn btn-primary"
              style={{ padding: "6px 14px", fontSize: "0.85rem", whiteSpace: "nowrap" }}
              onClick={() => handleBulkStatus(bulkStatus)}
              disabled={!bulkStatus || bulkLoading}
            >
              {bulkLoading ? "…" : "Setzen"}
            </button>
          </div>
          {bulkError && <p style={{ color: "var(--error)", fontSize: "0.8rem", width: "100%", margin: 0 }}>{bulkError}</p>}

          {/* Delete series */}
          <div style={{ width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 4 }}>
            {deleteConfirm ? (
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <span style={{ fontSize: "0.85rem", color: "var(--error)" }}>
                  Alle Einträge dieser Reihe löschen?
                </span>
                <button
                  className="btn"
                  style={{ padding: "4px 12px", fontSize: "0.85rem", background: "var(--error)", color: "#fff", border: "none" }}
                  onClick={handleDeleteSeries}
                  disabled={deleteLoading}
                >
                  {deleteLoading ? "…" : "Ja, löschen"}
                </button>
                <button className="btn btn-ghost" style={{ padding: "4px 10px", fontSize: "0.85rem" }} onClick={() => setDeleteConfirm(false)}>
                  Abbrechen
                </button>
              </div>
            ) : (
              <button
                className="btn btn-ghost"
                style={{ padding: "6px 12px", fontSize: "0.85rem", color: "var(--error)" }}
                onClick={() => setDeleteConfirm(true)}
              >
                Serie löschen
              </button>
            )}
            <button className="btn btn-ghost" onClick={onClose}>Schließen</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SeriesModal;
