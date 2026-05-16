import React from "react";

const StackIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ verticalAlign: "middle" }}>
    <rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 3H8a2 2 0 0 0-2 2v2h12V5a2 2 0 0 0-2-2z"/>
  </svg>
);

const ItemCardGrid = ({ displayItems, onSelect, onSelectSeries }) => (
  <div className="card-grid">
    {displayItems.map((item) => {
      if (item.type === "series") {
        const fallbackCover = item.entries.find((e) => e.item.cover_url);
        const coverUrl = item.seriesCover || fallbackCover?.item.cover_url || null;
        const cover = fallbackCover || item.entries[0];
        return (
          <article key={item.id} className="item-card series-group-card" onClick={() => onSelectSeries(item)}>
            <div style={{ position: "relative" }}>
              {coverUrl
                ? <img className="item-card-cover" src={coverUrl} alt={item.seriesName} />
                : <div className="item-card-cover-placeholder">📚</div>
              }
              <span className="series-count-badge">
                <StackIcon /> {item.entries.length}
              </span>
            </div>
            <div className="item-card-info">
              <h3>{item.seriesName}</h3>
              <p className="author">{cover.item.authors?.join(", ") || "—"}</p>
            </div>
            <div className="item-card-footer">
              <span className="status-badge series">{item.entries.length} Bände</span>
            </div>
          </article>
        );
      }

      const entry = item.entry;
      return (
        <article key={item.id} className="item-card" onClick={() => onSelect(entry)}>
          {entry.item.cover_url
            ? <img className="item-card-cover" src={entry.item.cover_url} alt={entry.item.title} />
            : <div className="item-card-cover-placeholder">📖</div>
          }
          <div className="item-card-info">
            <h3>{entry.item.title}</h3>
            <p className="author">{entry.item.authors?.join(", ") || "—"}</p>
          </div>
          <div className="item-card-footer">
            <span className={`status-badge ${entry.status}`}>{entry.status}</span>
            {entry.item.page_count > 0 && (
              <div className="progress-bar-wrap">
                <div className="progress-bar" style={{ width: `${entry.progress_percent}%` }} />
              </div>
            )}
          </div>
        </article>
      );
    })}
  </div>
);

export default ItemCardGrid;
