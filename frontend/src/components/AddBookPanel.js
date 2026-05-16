import React, { useState, useEffect, useRef } from "react";
import { importISBN, createUserEntry } from "../api";
import { STATUS_OPTIONS, capitalize } from "../constants";

const SCAN_STEPS = [
  { id: "dnb",         label: "Deutsche Nationalbibliothek" },
  { id: "google",      label: "Google Books / Open Library" },
  { id: "anilist",     label: "AniList (Manga-Covers)" },
  { id: "mangapassion",label: "Manga-Passion (Verlagsdaten)" },
];

const ScanProgress = ({ activeStep, done, source }) => (
  <div style={{
    margin: "12px 0", padding: "10px 14px", borderRadius: 8,
    background: "var(--surface-2)", border: "1px solid var(--border)",
  }}>
    <div style={{ fontSize: "0.78rem", color: "var(--text-3)", marginBottom: 8, fontWeight: 600, letterSpacing: "0.04em" }}>
      WIRD AUSGELESEN…
    </div>
    {SCAN_STEPS.map((step, idx) => {
      const isActive = idx === activeStep && !done;
      const isDone = done || idx < activeStep;
      return (
        <div key={step.id} style={{
          display: "flex", alignItems: "center", gap: 8,
          padding: "3px 0", fontSize: "0.85rem",
          color: isDone ? "var(--text-1)" : isActive ? "var(--accent)" : "var(--text-3)",
        }}>
          <span style={{ width: 16, textAlign: "center", flexShrink: 0 }}>
            {isDone ? "✓" : isActive ? "⟳" : "·"}
          </span>
          <span>{step.label}</span>
          {isActive && (
            <span style={{ color: "var(--text-3)", fontSize: "0.78rem" }}>lädt…</span>
          )}
          {done && idx === SCAN_STEPS.length - 1 && source && (
            <span style={{ color: "var(--text-3)", fontSize: "0.78rem", marginLeft: "auto" }}>
              via {source}
            </span>
          )}
        </div>
      );
    })}
  </div>
);

const BoxSetPreview = ({ preview }) => {
  const box = preview.box_set;
  const alreadyIds = new Set(preview.already_in_library_ids || []);
  const newCount = preview.box_volumes.filter((v) => !alreadyIds.has(v.id)).length;
  return (
    <div className="isbn-preview" style={{ flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", gap: 12 }}>
        {preview.cover_url
          ? <img src={preview.cover_url} alt={preview.title} style={{ width: 70, height: 100, objectFit: "cover", borderRadius: 6 }} />
          : (
            <div style={{
              width: 70, height: 100, background: "var(--bg-card)",
              borderRadius: 6, display: "flex", alignItems: "center",
              justifyContent: "center", color: "var(--text-3)",
            }}>
              📦
            </div>
          )
        }
        <div className="isbn-preview-info">
          <h4>{preview.title}</h4>
          {preview.authors?.length > 0 && <p>{preview.authors.join(", ")}</p>}
          <p style={{ color: "var(--accent)" }}>
            Sammelbox · Bände {box.volume_from}–{box.volume_to}
          </p>
          <p style={{ color: "var(--text-2)", fontSize: "0.85em" }}>
            {newCount > 0
              ? `${newCount} neue Bände werden hinzugefügt`
              : "Alle Bände bereits in deiner Bibliothek"}
          </p>
        </div>
      </div>
      {preview.box_volumes?.length > 0 && (
        <div style={{ fontSize: "0.82em", lineHeight: 1.8, display: "flex", flexWrap: "wrap", gap: "2px 8px" }}>
          {preview.box_volumes.map((v) => {
            const owned = alreadyIds.has(v.id);
            return (
              <span key={v.id} style={{
                color: owned ? "var(--text-3)" : "var(--text-1)",
                textDecoration: owned ? "line-through" : "none",
              }}>
                Band {v.volume_number}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};

const EMPTY_MANUAL = {
  title: "", authors: "", publication_year: "", genre: "",
  page_count: "", description: "", isbn: "", language: "",
};

const AddBookPanel = ({ onClose, onSaved }) => {
  const [tab, setTab] = useState("isbn");

  // ISBN tab state
  const [isbnInput,   setIsbnInput]   = useState("");
  const [preview,     setPreview]     = useState(null);
  const [isbnLoading, setIsbnLoading] = useState(false);
  const [isbnError,   setIsbnError]   = useState(null);
  const [isbnStatus,  setIsbnStatus]  = useState("unread");
  const [scanStep,    setScanStep]    = useState(-1);   // -1 = idle
  const [scanDone,    setScanDone]    = useState(false);
  const stepTimers = useRef([]);

  // Manual tab state
  const [manual,        setManual]        = useState(EMPTY_MANUAL);
  const [manualStatus,  setManualStatus]  = useState("unread");
  const [manualLoading, setManualLoading] = useState(false);
  const [manualError,   setManualError]   = useState(null);

  const [saving, setSaving] = useState(false);

  // ── ISBN flow ────────────────────────────────────────────────────────────
  const handleIsbnFetch = async (e) => {
    e.preventDefault();
    // Clear previous state
    stepTimers.current.forEach(clearTimeout);
    stepTimers.current = [];
    setIsbnLoading(true); setIsbnError(null); setPreview(null);
    setScanStep(0); setScanDone(false);

    // Animate through steps while request is in-flight (rough timing match)
    const delays = [0, 900, 1800, 2700];
    delays.forEach((delay, idx) => {
      stepTimers.current.push(setTimeout(() => setScanStep(idx), delay));
    });

    try {
      const res = await importISBN(isbnInput.trim());
      setScanDone(true);
      setScanStep(SCAN_STEPS.length - 1);
      setPreview(res.data);
    } catch (err) {
      setScanStep(-1);
      setIsbnError(err.response?.data?.detail || "Could not find this ISBN");
    } finally {
      stepTimers.current.forEach(clearTimeout);
      stepTimers.current = [];
      setIsbnLoading(false);
    }
  };

  const handleIsbnSave = async () => {
    if (!preview) return;
    setSaving(true);
    try {
      if (preview.type === "boxset") {
        const alreadyIds = new Set(preview.already_in_library_ids || []);
        for (const vol of preview.box_volumes) {
          if (!alreadyIds.has(vol.id)) {
            await createUserEntry({ item_id: vol.id, status: isbnStatus, current_page: 0 });
          }
        }
      } else {
        await createUserEntry({ item_id: preview.id, status: isbnStatus, current_page: 0 });
      }
      onSaved();
      onClose();
    } catch (err) {
      setIsbnError(err.response?.data?.detail || "Could not add to library");
    } finally {
      setSaving(false);
    }
  };

  // ── Manual flow ──────────────────────────────────────────────────────────
  const handleManualSave = async (e) => {
    e.preventDefault();
    setManualLoading(true); setManualError(null);
    try {
      const item = {
        title: manual.title,
        authors: manual.authors
          ? manual.authors.split(",").map((a) => a.trim()).filter(Boolean)
          : [],
        publication_year: manual.publication_year ? parseInt(manual.publication_year) : null,
        genre:       manual.genre       || null,
        page_count:  manual.page_count  ? parseInt(manual.page_count) : null,
        description: manual.description || null,
        isbn:        manual.isbn        || null,
        language:    manual.language    || null,
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
            <button
              className={`add-tab ${tab === "isbn" ? "active" : ""}`}
              onClick={() => setTab("isbn")}
            >
              ISBN / Barcode
            </button>
            <button
              className={`add-tab ${tab === "manual" ? "active" : ""}`}
              onClick={() => setTab("manual")}
            >
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
                      required
                      autoFocus
                    />
                    <button className="btn btn-primary" type="submit" disabled={isbnLoading}>
                      {isbnLoading ? "…" : "Look up"}
                    </button>
                  </div>
                </div>
              </form>

              {isbnLoading && scanStep >= 0 && (
                <ScanProgress activeStep={scanStep} done={false} source={null} />
              )}

              {isbnError && <div className="alert alert-error">{isbnError}</div>}

              {preview && !isbnLoading && scanDone && scanStep >= 0 && (
                <ScanProgress activeStep={SCAN_STEPS.length - 1} done source={preview.source} />
              )}

              {preview && (
                <>
                  {preview.type === "boxset" ? (
                    <BoxSetPreview preview={preview} />
                  ) : (
                    <div className="isbn-preview">
                      {preview.cover_url
                        ? <img src={preview.cover_url} alt={preview.title} />
                        : (
                          <div style={{
                            width: 70, height: 100, background: "var(--bg-card)",
                            borderRadius: 6, display: "flex", alignItems: "center",
                            justifyContent: "center", color: "var(--text-3)",
                          }}>
                            📖
                          </div>
                        )
                      }
                      <div className="isbn-preview-info">
                        <h4>{preview.title}</h4>
                        <p>{preview.authors?.join(", ")}</p>
                        <p>
                          {preview.publication_year || ""}
                          {preview.genre ? ` · ${preview.genre}` : ""}
                        </p>
                        {preview.page_count && <p>{preview.page_count} pages</p>}
                        {preview.already_in_library && (
                          <p style={{
                            color: "var(--accent)", fontWeight: 600,
                            fontSize: "0.82em", marginTop: 4,
                          }}>
                            ✓ Bereits in deiner Bibliothek
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                  {!preview.already_in_library && !(preview.type === "boxset" && preview.volume_count > 0 && (preview.already_in_library_ids?.length ?? 0) >= preview.volume_count) && (
                    <div className="field" style={{ marginTop: 16 }}>
                      <label>Hinzufügen als</label>
                      <select value={isbnStatus} onChange={(e) => setIsbnStatus(e.target.value)}>
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s}>{capitalize(s)}</option>
                        ))}
                      </select>
                    </div>
                  )}
                </>
              )}
            </>
          )}

          {tab === "manual" && (
            <form id="manual-form" onSubmit={handleManualSave}>
              {manualError && (
                <div className="alert alert-error" style={{ marginBottom: 16 }}>{manualError}</div>
              )}
              <div className="field">
                <label>Title *</label>
                <input value={manual.title} onChange={setField("title")} required autoFocus />
              </div>
              <div className="field">
                <label>
                  Authors{" "}
                  <span style={{ color: "var(--text-3)", fontWeight: 400 }}>(comma-separated)</span>
                </label>
                <input
                  value={manual.authors}
                  onChange={setField("authors")}
                  placeholder="e.g. Frank Herbert, Arthur C. Clarke"
                />
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Year</label>
                  <input
                    type="number"
                    value={manual.publication_year}
                    onChange={setField("publication_year")}
                    min="1000" max="2100"
                  />
                </div>
                <div className="field">
                  <label>Pages</label>
                  <input
                    type="number"
                    value={manual.page_count}
                    onChange={setField("page_count")}
                    min="1"
                  />
                </div>
              </div>
              <div className="field-row">
                <div className="field">
                  <label>Genre</label>
                  <input value={manual.genre} onChange={setField("genre")} />
                </div>
                <div className="field">
                  <label>Language</label>
                  <input
                    value={manual.language}
                    onChange={setField("language")}
                    placeholder="e.g. en, de, ja"
                  />
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
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s} value={s}>{capitalize(s)}</option>
                  ))}
                </select>
              </div>
            </form>
          )}
        </div>

        <div className="modal-footer">
          <button className="btn btn-ghost" onClick={onClose}>Cancel</button>
          {tab === "isbn" && preview && (() => {
            const allOwned = preview.already_in_library ||
              (preview.type === "boxset" && preview.volume_count > 0 && (preview.already_in_library_ids?.length ?? 0) >= preview.volume_count);
            return allOwned ? (
              <span style={{ color: "var(--text-3)", fontSize: "0.9em", alignSelf: "center" }}>
                Bereits in der Bibliothek
              </span>
            ) : (
              <button className="btn btn-primary" onClick={handleIsbnSave} disabled={saving}>
                {saving ? "Wird hinzugefügt…" : "Zur Bibliothek hinzufügen"}
              </button>
            );
          })()}
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
