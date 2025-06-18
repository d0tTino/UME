const { useState, useRef } = React;

function App() {
  const [token, setToken] = useState('');
  const [vector, setVector] = useState('');
  const [cypher, setCypher] = useState('');
  const [queryResult, setQueryResult] = useState('');
  const [searchResult, setSearchResult] = useState('');
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
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
      .then((data) =>
        setSearchResult(
          Array.isArray(data.ids)
            ? data.ids.join(', ')
            : JSON.stringify(data, null, 2)
        )
      )
      .catch((err) => console.error('Search failed', err));
  }

  function runQuery() {
    if (!cypher) return;
    fetch('/query?cypher=' + encodeURIComponent(cypher), {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((res) => res.json())
      .then((data) => setQueryResult(JSON.stringify(data, null, 2)))
      .catch((err) => console.error('Query failed', err));
  }

  function loadStats() {
    fetch('/dashboard/stats', {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((res) => res.json())
      .then((data) => setStats(data))
      .catch((err) => console.error('Failed to load stats', err));
  }

  function loadEvents() {
    fetch('/dashboard/recent_events', {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((res) => res.json())
      .then((data) => setEvents(data))
      .catch((err) => console.error('Failed to load events', err));
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
        placeholder: 'Cypher query',
        value: cypher,
        onChange: (e) => setCypher(e.target.value),
        style: { marginLeft: '8px', width: '40%' },
      }),
      React.createElement(
        'button',
        { onClick: runQuery, style: { marginLeft: '4px' } },
        'Run Query'
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
      ),
      React.createElement(
        'button',
        { onClick: loadStats, style: { marginLeft: '4px' } },
        'Load Stats'
      ),
      React.createElement(
        'button',
        { onClick: loadEvents, style: { marginLeft: '4px' } },
        'Recent Events'
      )
    ),
    React.createElement(
      'pre',
      { style: { margin: 0, padding: '8px' } },
      queryResult
    ),
    React.createElement(
      'pre',
      { style: { margin: 0, padding: '8px' } },
      searchResult
    ),
    stats &&
      React.createElement(
        'pre',
        { style: { margin: 0, padding: '8px' } },
        JSON.stringify(stats, null, 2)
      ),
    events.length > 0 &&
      React.createElement(
        'pre',
        { style: { margin: 0, padding: '8px' } },
        JSON.stringify(events, null, 2)
      ),
    React.createElement('div', { ref: containerRef, style: { flex: 1 } })
  );
}

ReactDOM.render(React.createElement(App), document.getElementById('root'));
