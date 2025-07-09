import { useEffect, useState } from 'react';

export default function GraphView({ token }) {
  const [graph, setGraph] = useState(null);

  const load = async () => {
    const res = await fetch('/ledger/replay', {
      headers: { Authorization: 'Bearer ' + token },
    });
    if (res.ok) setGraph(await res.json());
  };

  useEffect(() => {
    if (token) load();
  }, [token]);

  if (!token) return null;

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Graph</h3>
      <button onClick={load}>Refresh</button>
      {graph && (
        <>
          <h4>Nodes</h4>
          <ul>
            {Object.entries(graph.nodes).map(([id, attrs]) => (
              <li key={id}>
                {id} {JSON.stringify(attrs)}
              </li>
            ))}
          </ul>
          <h4>Edges</h4>
          <ul>
            {graph.edges.map(([s, t, l]) => (
              <li key={`${s}-${t}-${l}`}>{s} -[{l}]-&gt; {t}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
