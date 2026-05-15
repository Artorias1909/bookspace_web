import React, { useState, useEffect } from "react";
import { createUserEntry, updateItem, updateUserEntry } from "../api";

const STATUS_OPTIONS = ["unread", "reading", "completed", "owned", "wishlist"];

const ItemDetailModal = ({ entry, onClose, onSaved }) => {
  const [itemData, setItemData] = useState(entry.item);
  const [status, setStatus] = useState(entry.status || "unread");
  const [currentPage, setCurrentPage] = useState(entry.current_page || 0);
  const [message, setMessage] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setItemData(entry.item);
    setStatus(entry.status || "unread");
    setCurrentPage(entry.current_page || 0);
    setMessage(null);
  }, [entry]);

  const saveChanges = async () => {
    setSaving(true); setMessage(null);
    try {
      if (entry.isImport) {
        await createUserEntry({ item: itemData, status, current_page: currentPage });
      } else {
        await updateUserEntry(entry.id, { current_page: currentPage, status });
        await updateItem(itemData.id, itemData);
      }
      setMessage({ type: "success", text: "Saved." });
      onSaved();
    } catch {
      setMessage({ type: "error", text: "Could not save changes." });
    } finally {
      setSaving(false);
    }
  };

  const setField = (key) => (e) =>
    setItemData((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 style={{ fontSize: "1rem" }}>{itemData.title}</h2>
          <button className="btn btn-ghost" style={{ padding: "6px 12px" }} onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          <div className="detail-grid">
            {/* Cover */}
            <div>
              {itemData.cover_url
                ? <img className="detail-cover" src={itemData.cover_url} alt={itemData.title} />
                : <div className="detail-cover-placeholder">📖</div>
              }
            </div>

            {/* Details */}
            <div className="detail-meta">
              <div className="detail-meta-row">
                <strong>Author(s)</strong>
                <span>{itemData.authors?.join(", ") || "—"}</span>
              </div>
              <div className="detail-meta-row">
                <strong>Genre</strong>
                <span>{itemData.genre || "—"}</span>
              </div>
              <div className="detail-meta-row">
                <strong>Year</strong>
                <span>{itemData.publication_year || "—"}</span>
              </div>
              <div className="detail-meta-row">
                <strong>Language</strong>
                <span>{itemData.language || "—"}</span>
              </div>
              {itemData.isbn && (
                <div className="detail-meta-row">
                  <strong>ISBN</strong>
                  <span>{itemData.isbn}</span>
                </div>
              )}
              {itemData.volume_title && (
                <div className="detail-meta-row">
                  <strong>Series</strong>
                  <span>{itemData.volume_title}{itemData.volume_number && ` — Vol. ${itemData.volume_number}`}</span>
                </div>
              )}

              <div className="divider" />

              <div className="field">
                <label>Status</label>
                <select value={status} onChange={(e) => setStatus(e.target.value)}>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                  ))}
                </select>
              </div>

              <div className="field">
                <label>
                  Current page
                  {itemData.page_count && <span style={{ color: "var(--text-3)", fontWeight: 400 }}> / {itemData.page_count}</span>}
                </label>
                <input
                  type="number" min={0} max={itemData.page_count || undefined}
                  value={currentPage}
                  onChange={(e) => setCurrentPage(Number(e.target.value))}
                />
              </div>

              {itemData.page_count > 0 && (
                <div>
                  <div className="progress-bar-wrap" style={{ height: 6 }}>
                    <div className="progress-bar" style={{ width: `${Math.min(currentPage / itemData.page_count * 100, 100).toFixed(1)}%` }} />
                  </div>
                  <p style={{ fontSize: "0.8rem", color: "var(--text-3)", marginTop: 4 }}>
                    {Math.min(currentPage / itemData.page_count * 100, 100).toFixed(0)}% read
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Description */}
          {itemData.description && (
            <div className="detail-description">
              <h4>Description</h4>
              <p>{itemData.description}</p>
            </div>
          )}

          {message && (
            <div className={`alert alert-${message.type}`} style={{ marginTop: 16 }}>{message.text}</div>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Close</button>
          <button className="btn btn-primary" onClick={saveChanges} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
};

export default ItemDetailModal;
