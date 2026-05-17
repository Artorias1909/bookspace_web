import React, { useState } from "react";

const ISBNImportForm = ({ onImport }) => {
  const [isbn, setIsbn] = useState("");
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    try {
      await onImport(isbn.trim());
      setIsbn("");
      setError(null);
    } catch (err) {
      setError(err.response?.data?.detail || "Unable to import ISBN");
    }
  };

  return (
    <form className="isbn-form card" onSubmit={handleSubmit}>
      <label>
        ISBN / Barcode
        <input
          type="text"
          value={isbn}
          onChange={(e) => setIsbn(e.target.value)}
          placeholder="Enter ISBN and press Enter"
          required
        />
      </label>
      <button type="submit">Import Metadata</button>
      {error && <div className="alert">{error}</div>}
    </form>
  );
};

export default ISBNImportForm;
