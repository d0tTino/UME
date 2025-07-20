import { useEffect, useRef } from 'react';
import { Network } from 'vis-network/standalone';

export default function GraphNetwork({ token }) {
  const container = useRef(null);

  useEffect(() => {
    if (!token) return;
    const load = async () => {
      const res = await fetch('/graph/dump', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (!res.ok) return;
      const data = await res.json();
      const nodes = Object.keys(data.nodes).map((id) => ({ id, label: id }));
      const edges = data.edges.map(([from, to, label]) => ({ from, to, label }));
      new Network(container.current, { nodes, edges }, {});
    };
    load();
  }, [token]);

  if (!token) return null;
  return (
    <div style={{ marginTop: '8px' }}>
      <div ref={container} style={{ height: '400px' }}></div>
    </div>
  );
}
