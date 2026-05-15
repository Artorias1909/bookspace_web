import React from "react";

const ItemTable = ({ entries, onSelect }) => (
  <div className="table-wrap">
    <table className="item-table">
      <thead>
        <tr>
          <th style={{ width: 52 }}></th>
          <th>Title</th>
          <th>Author</th>
          <th>Year</th>
          <th>Status</th>
          <th>Progress</th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={entry.id} onClick={() => onSelect(entry)}>
            <td>
              {entry.item.cover_url
                ? <img className="table-cover" src={entry.item.cover_url} alt={entry.item.title} />
                : <div className="table-cover-placeholder">📖</div>
              }
            </td>
            <td><strong>{entry.item.title}</strong>{entry.item.volume_number && <span style={{ color: "var(--text-3)", marginLeft: 6 }}>Vol. {entry.item.volume_number}</span>}</td>
            <td style={{ color: "var(--text-2)" }}>{entry.item.authors?.join(", ") || "—"}</td>
            <td style={{ color: "var(--text-2)" }}>{entry.item.publication_year || "—"}</td>
            <td><span className={`status-badge ${entry.status}`}>{entry.status}</span></td>
            <td>
              {entry.item.page_count > 0 ? (
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div className="table-progress-wrap">
                    <div className="table-progress" style={{ width: `${entry.progress_percent}%` }} />
                  </div>
                  <span style={{ color: "var(--text-3)", fontSize: "0.8rem", minWidth: 34 }}>{entry.progress_percent}%</span>
                </div>
              ) : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

export default ItemTable;
