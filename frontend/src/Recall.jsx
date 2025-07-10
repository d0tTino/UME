import { useState } from 'react';

export default function Recall({ token }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [score, setScore] = useState(null);

  const search = async () => {
    if (!query) return;
    const params = new URLSearchParams({ query });
    const res = await fetch(`/recall?${params}`, {
      headers: { Authorization: 'Bearer ' + token },
    });
    if (res.ok) {
      const data = await res.json();
      setResults(data.nodes || []);
      const mres = await fetch('/metrics/summary', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (mres.ok) {
        const sum = await mres.json();
        setScore(sum.average_recall_score);
      }
    }
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Recall</h3>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <button onClick={search} style={{ marginLeft: '4px' }}>
        Search
      </button>
      {score !== null && (
        <div>Average recall score: {score.toFixed(3)}</div>
      )}
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
