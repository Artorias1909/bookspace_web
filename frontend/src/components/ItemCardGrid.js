import React from "react";

const ItemCardGrid = ({ entries, onSelect }) => (
  <div className="card-grid">
    {entries.map((entry) => (
      <article key={entry.id} className="item-card" onClick={() => onSelect(entry)}>
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
    ))}
  </div>
);

export default ItemCardGrid;
