const { useEffect, useRef } = React;

function Graph() {
  const containerRef = useRef(null);
  useEffect(() => {
    const nodes = new vis.DataSet([
      { id: 1, label: 'Node 1' },
      { id: 2, label: 'Node 2' },
      { id: 3, label: 'Node 3' },
    ]);

    const edges = new vis.DataSet([
      { from: 1, to: 2 },
      { from: 2, to: 3 },
    ]);

    const data = { nodes, edges };
    const options = { physics: { stabilization: true } };
    new vis.Network(containerRef.current, data, options);
  }, []);
  return React.createElement('div', { style: { height: '100%' }, ref: containerRef });
}

ReactDOM.render(React.createElement(Graph), document.getElementById('root'));
