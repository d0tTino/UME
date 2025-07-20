import NodeSearch from './NodeSearch';
import GraphView from './GraphView';

export default function GraphExplorer({ token }) {
  if (!token) return null;
  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Graph Explorer</h3>
      <NodeSearch token={token} />
      <GraphView token={token} />
    </div>
  );
}
