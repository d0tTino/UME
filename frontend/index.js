const { useState, useRef, useEffect } = React;

function App() {
  const [token, setToken] = useState('');
  const [vector, setVector] = useState('');
  const containerRef = useRef(null);
  const networkRef = useRef(null);

  function loadGraph() {
    fetch('/analytics/subgraph', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer ' + token,
      },
      body: JSON.stringify({ start: 'a', depth: 1 }),
    })
      .then((res) => res.json())
      .then((data) => {
        const nodes = new vis.DataSet(
          Object.keys(data.nodes).map((id) => ({ id, label: id }))
        );
        const edges = new vis.DataSet(
          data.edges.map((e) => ({ from: e.source, to: e.target }))
        );
        const graphData = { nodes, edges };
        const options = { physics: { stabilization: true } };
        if (networkRef.current) {
          networkRef.current.setData(graphData);
        } else {
          networkRef.current = new vis.Network(
            containerRef.current,
            graphData,
            options
          );
        }
      })
      .catch((err) => console.error('Failed to load graph', err));
  }

  function searchVectors() {
    if (!vector) return;
    const params = vector
      .split(',')
      .map((v) => 'vector=' + encodeURIComponent(v.trim()))
      .join('&');
    fetch('/vectors/search?' + params, {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((res) => res.json())
      .then((data) => alert('Results: ' + data.ids.join(', ')))
      .catch((err) => console.error('Search failed', err));
  }

  return React.createElement(
    'div',
    { style: { height: '100%', display: 'flex', flexDirection: 'column' } },
    React.createElement(
      'div',
      { style: { padding: '8px', background: '#eee' } },
      React.createElement('input', {
        placeholder: 'API Token',
        value: token,
        onChange: (e) => setToken(e.target.value),
      }),
      React.createElement(
        'button',
        { onClick: loadGraph, style: { marginLeft: '4px' } },
        'Load Graph'
      ),
      React.createElement('input', {
        placeholder: 'Vector search',
        value: vector,
        onChange: (e) => setVector(e.target.value),
        style: { marginLeft: '8px' },
      }),
      React.createElement(
        'button',
        { onClick: searchVectors, style: { marginLeft: '4px' } },
        'Search'
      )
    ),
    React.createElement('div', { ref: containerRef, style: { flex: 1 } })
  );
}

ReactDOM.render(React.createElement(App), document.getElementById('root'));
