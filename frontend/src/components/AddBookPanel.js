import React, { useState } from "react";
import { importISBN, createUserEntry } from "../api";

const STATUS_OPTIONS = ["unread", "reading", "completed", "owned", "wishlist"];

const EMPTY_MANUAL = {
  title: "", authors: "", publication_year: "", genre: "",
  page_count: "", description: "", isbn: "", language: "",
};

const AddBookPanel = ({ onClose, onSaved }) => {
  const [tab, setTab] = useState("isbn");

  // ISBN tab state
  const [isbnInput, setIsbnInput] = useState("");
  const [preview, setPreview] = useState(null);
  const [isbnLoading, setIsbnLoading] = useState(false);
  const [isbnError, setIsbnError] = useState(null);
  const [isbnStatus, setIsbnStatus] = useState("unread");

  // Manual tab state
  const [manual, setManual] = useState(EMPTY_MANUAL);
  const [manualStatus, setManualStatus] = useState("unread");
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError, setManualError] = useState(null);

  const [saving, setSaving] = useState(false);

  // ── ISBN flow ───────────────────────────────────────────────
  const handleIsbnFetch = async (e) => {
    e.preventDefault();
    setIsbnLoading(true); setIsbnError(null); setPreview(null);
    try {
      const res = await importISBN(isbnInput.trim());
      setPreview(res.data);
    } catch (err) {
      setIsbnError(err.response?.data?.detail || "Could not find this ISBN");
    } finally {
      setIsbnLoading(false);
    }
  };

  const handleIsbnSave = async () => {
    if (!preview) return;
    setSaving(true);
    try {
      await createUserEntry({ item_id: preview.id, status: isbnStatus, current_page: 0 });
      onSaved();
      onClose();
    } catch (err) {
      setIsbnError(err.response?.data?.detail || "Could not add to library");
    } finally {
      setSaving(false);
    }
  };

  // ── Manual flow ─────────────────────────────────────────────
  const handleManualSave = async (e) => {
    e.preventDefault();
    setManualLoading(true); setManualError(null);
    try {
      const item = {
        title: manual.title,
        authors: manual.authors ? manual.authors.split(",").map((a) => a.trim()).filter(Boolean) : [],
        publication_year: manual.publication_year ? parseInt(manual.publication_year) : null,
        genre: manual.genre || null,
        page_count: manual.page_count ? parseInt(manual.page_count) : null,
        description: manual.description || null,
        isbn: manual.isbn || null,
        language: manual.language || null,
      };
      await createUserEntry({ item, status: manualStatus, current_page: 0 });
      onSaved();
      onClose();
    } catch (err) {
      setManualError(err.response?.data?.detail || "Could not add book");
    } finally {
      setManualLoading(false);
    }
  };

  const setField = (key) => (e) => setManual((prev) => ({ ...prev, [key]: e.target.value }));

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" style={{ maxWidth: 560 }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Add book</h2>
          <button className="btn btn-ghost" style={{ padding: "6px 12px" }} onClick={onClose}>✕</button>
        </div>
        <div className="modal-body">
          <div className="add-tabs">
            <button className={`add-tab ${tab === "isbn" ? "active" : ""}`} onClick={() => setTab("isbn")}>
              ISBN / Barcode
            </button>
            <button className={`add-tab ${tab === "manual" ? "active" : ""}`} onClick={() => setTab("manual")}>
              Manual entry
            </button>
          </div>

          {tab === "isbn" && (
            <>
              <form onSubmit={handleIsbnFetch}>
                <div className="field">
                  <label>ISBN-10 or ISBN-13</label>
                  <div className="isbn-input-row">
                    <input
                      value={isbnInput}
                      onChange={(e) => setIsbnInput(e.target.value)}
                      placeholder="e.g. 9783453317796"
                      required autoFocus
                    />
                    <button className="btn btn-primary" type="submit" disabled={isbnLoading}>
                      {isbnLoading ? "…" : "Look up"}
                    </button>
                  </div>
                </div>
              </form>

              {isbnError && <div className="alert alert-error">{isbnError}</div>}

              {preview && (
                <>
                  <div className="isbn-preview">
                    {preview.cover_url
                      ? <img src={preview.cover_url} alt={preview.title} />
                      : <div style={{ width: 70, height: 100, background: "var(--bg-card)", borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-3)" }}>📖</div>
                    }
                    <div className="isbn-preview-info">
                      <h4>{preview.title}</h4>
                      <p>{preview.authors?.join(", ")}</p>
                      <p>{preview.publication_year || ""} {preview.genre ? `· ${preview.genre}` : ""}</p>
                      {preview.page_count && <p>{preview.page_count} pages</p>}
                    </div>
                  </div>
                  <div className="field" style={{ marginTop: 16 }}>
                    <label>Add to library as</label>
                    <select value={isbnStatus} onChange={(e) => setIsbnStatus(e.target.value)}>
                      {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                    </select>
                  </div>
                </>
              )}
            </>
          )}

          {tab === "manual" && (
            <form id="manual-form" onSubmit={handleManualSave}>
              {manualError && <div className="alert alert-error" style={{ marginBottom: 16 }}>{manualError}</div>}
              <div className="field">
                <label>Title *</label>
                <input value={manual.title} onChange={setField("title")} required autoFocus />
              </div>
              <div className="field">
                <label>Authors <span style={{ color: "var(--text-3)", fontWeight: 400 }}>(comma-separated)</span></label>
                <input value={manual.authors} onChange={setField("authors")} placeholder="e.g. Frank Herbert, Arthur C. Clarke" />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Year</label>
                  <input type="number" value={manual.publication_year} onChange={setField("publication_year")} min="1000" max="2100" />
                </div>
                <div className="field">
                  <label>Pages</label>
                  <input type="number" value={manual.page_count} onChange={setField("page_count")} min="1" />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Genre</label>
                  <input value={manual.genre} onChange={setField("genre")} />
                </div>
                <div className="field">
                  <label>Language</label>
                  <input value={manual.language} onChange={setField("language")} placeholder="e.g. en, de, ja" />
                </div>
              </div>
              <div className="field">
                <label>ISBN</label>
                <input value={manual.isbn} onChange={setField("isbn")} />
              </div>
              <div className="field">
                <label>Description</label>
                <textarea value={manual.description} onChange={setField("description")} />
              </div>
              <div className="field">
                <label>Add to library as</label>
                <select value={manualStatus} onChange={(e) => setManualStatus(e.target.value)}>
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>)}
                </select>
              </div>
            </form>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {tab === "isbn" && preview && (
            <button className="btn btn-primary" onClick={handleIsbnSave} disabled={saving}>
              {saving ? "Adding…" : "Add to library"}
            </button>
          )}
          {tab === "manual" && (
            <button className="btn btn-primary" type="submit" form="manual-form" disabled={manualLoading}>
              {manualLoading ? "Adding…" : "Add to library"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default AddBookPanel;
