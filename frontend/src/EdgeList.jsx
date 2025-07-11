import { useEffect, useState } from 'react';

export default function EdgeList({ token }) {
  const [edges, setEdges] = useState([]);

  const load = async () => {
    const res = await fetch('/ledger/replay', {
      headers: { Authorization: 'Bearer ' + token },
    });
    if (res.ok) {
      const data = await res.json();
      setEdges(data.edges || []);
    }
  };

  useEffect(() => {
    if (token) load();
  }, [token]);

  if (!token) return null;

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Edges</h3>
      <button onClick={load}>Refresh</button>
      <ul>
        {edges.map(([s, t, l]) => (
          <li key={`${s}-${t}-${l}`}>{s} -[{l}]-&gt; {t}</li>
        ))}
      </ul>
    </div>
  );
}
