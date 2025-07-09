import { useState } from 'react';

export default function Recall({ token }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);

  const search = async () => {
    if (!query) return;
    const params = new URLSearchParams({ query });
    const res = await fetch(`/recall?${params}`, {
      headers: { Authorization: 'Bearer ' + token },
    });
    if (res.ok) {
      const data = await res.json();
      setResults(data.nodes || []);
    }
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Recall</h3>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <button onClick={search} style={{ marginLeft: '4px' }}>
        Search
      </button>
      <ul>
        {results.map((n) => (
          <li key={n.id}>
            {n.id} {JSON.stringify(n.attributes)}
          </li>
        ))}
      </ul>
    </div>
  );
}
