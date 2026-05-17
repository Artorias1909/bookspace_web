import React from "react";

const ItemTable = ({ displayItems, onSelect, onSelectSeries }) => (
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
        {displayItems.map((item) => {
          if (item.type === "series") {
            const fallbackCover = item.entries.find((e) => e.item.cover_url);
            const coverUrl = item.seriesCover || fallbackCover?.item.cover_url || null;
            const cover = fallbackCover || item.entries[0];
            return (
              <tr key={item.id} onClick={() => onSelectSeries(item)} className="series-group-row">
                <td>
                  {coverUrl
                    ? <img className="table-cover" src={coverUrl} alt={item.seriesName} />
                    : <div className="table-cover-placeholder">📚</div>
                  }
                </td>
                <td>
                  <strong>{item.seriesName}</strong>
                  <span style={{ color: "var(--text-3)", marginLeft: 6, fontSize: "0.8rem" }}>
                    {item.entries.length} Bände
                  </span>
                </td>
                <td style={{ color: "var(--text-2)" }}>{cover.item.authors?.join(", ") || "—"}</td>
                <td style={{ color: "var(--text-2)" }}>—</td>
                <td><span className="status-badge series">{item.entries.length} Bände</span></td>
                <td>—</td>
              </tr>
            );
          }

          const entry = item.entry;
          return (
            <tr key={item.id} onClick={() => onSelect(entry)}>
              <td>
                {entry.item.cover_url
                  ? <img className="table-cover" src={entry.item.cover_url} alt={entry.item.title} />
                  : <div className="table-cover-placeholder">📖</div>
                }
              </td>
              <td>
                <strong>{entry.item.title}</strong>
                {entry.item.volume_number && (
                  <span style={{ color: "var(--text-3)", marginLeft: 6 }}>Vol. {entry.item.volume_number}</span>
                )}
              </td>
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
          );
        })}
      </tbody>
    </table>
  </div>
);

export default ItemTable;
