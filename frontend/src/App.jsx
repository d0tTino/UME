import { useState, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import PiiStatus from './PiiStatus';
import PolicyEditor from './PolicyEditor';
import Recommendations from './Recommendations';
import ConsentLedger from './ConsentLedger';
import Recall from './Recall';
import GraphView from './GraphView';
import GraphNetwork from './GraphNetwork';
import NodeSearch from './NodeSearch';
import EdgeList from './EdgeList';
import LedgerHistory from './LedgerHistory';
import { createDashboardStreamClient } from './realtimeStream';

const POLICY_CONTENT = {
  'allow.rego': `package ume

default allow = false

allow {
    not forbidden_node
    not admin_role_update
    not admin_edge
}
`,
  'deny_admin_role.rego': `package ume

admin_role_update {
    input.event_type == "UPDATE_NODE_ATTRIBUTES"
    input.payload.attributes.role == "admin"
}
`,
  'deny_forbidden_node.rego': `package ume

forbidden_node {
    input.event_type == "CREATE_NODE"
    input.payload.node_id == "forbidden"
}
`,
  'extra/deny_admin_edge.rego': `package ume

admin_edge {
    input.event_type == "CREATE_EDGE"
    input.node_id == "admin"
}
`,
};

const STREAM_ENABLED = import.meta.env.VITE_ENABLE_DASHBOARD_STREAM !== 'false';
const STREAM_TRANSPORT = import.meta.env.VITE_DASHBOARD_STREAM_TRANSPORT || 'sse';
const REST_FALLBACK = import.meta.env.VITE_DASHBOARD_REST_FALLBACK !== 'false';

function App() {
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [redactedCount, setRedactedCount] = useState(0);
  const [streamStatus, setStreamStatus] = useState('rest');
  const [policies, setPolicies] = useState([]);
  const [editingPolicy, setEditingPolicy] = useState('');

  const authHeaders = { Authorization: 'Bearer ' + token };

  const login = async (e) => {
    e.preventDefault();
    const res = await fetch('/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }),
    });
    const data = await res.json();
    setToken(data.access_token);
  };

  const loadStats = async () => {
    const res = await fetch('/dashboard/stats', { headers: authHeaders });
    if (res.ok) setStats(await res.json());
  };

  const loadEvents = async () => {
    const res = await fetch('/dashboard/recent_events', { headers: authHeaders });
    if (res.ok) setEvents(await res.json());
  };

  const loadRedactions = async () => {
    const res = await fetch('/pii/redactions', { headers: authHeaders });
    if (res.ok) {
      const data = await res.json();
      setRedactedCount(data.redacted || 0);
    }
  };

  const loadPolicies = async () => {
    const res = await fetch('/policies', { headers: authHeaders });
    if (res.ok) {
      const data = await res.json();
      const active = new Set(data.policies);
      setPolicies(Object.keys(POLICY_CONTENT).map((name) => ({ name, enabled: active.has(name) })));
    }
  };

  useEffect(() => {
    if (!token) return;

    loadPolicies();

    if (!STREAM_ENABLED) {
      setStreamStatus('rest');
      void loadStats();
      void loadEvents();
      void loadRedactions();
      return;
    }

    const streamClient = createDashboardStreamClient({ transport: STREAM_TRANSPORT });
    setStreamStatus(`connecting:${STREAM_TRANSPORT}`);
    const unsubscribe = streamClient.subscribe({
      token,
      onDigest: (digest) => {
        setStats(digest.stats);
        setEvents(digest.recent_events);
        setRedactedCount(digest.redacted_count);
        setStreamStatus(`connected:${STREAM_TRANSPORT}`);
      },
      onControl: (control) => {
        if (control.kind === 'backpressure' && REST_FALLBACK) {
          void loadStats();
          void loadEvents();
          void loadRedactions();
        }
      },
      onError: () => {
        if (REST_FALLBACK) {
          setStreamStatus(`rest-fallback:${STREAM_TRANSPORT}`);
          void loadStats();
          void loadEvents();
          void loadRedactions();
          return;
        }
        setStreamStatus(`error:${STREAM_TRANSPORT}`);
      },
      onReconnect: () => setStreamStatus(`reconnecting:${STREAM_TRANSPORT}`),
    });

    return () => unsubscribe();
  }, [token]);

  const togglePolicy = async (name) => {
    const p = policies.find((x) => x.name === name);
    if (!p) return;
    if (p.enabled) {
      await fetch(`/policies/${name}`, { method: 'DELETE', headers: authHeaders });
    } else {
      const form = new FormData();
      const blob = new Blob([POLICY_CONTENT[name]], { type: 'text/plain' });
      form.append('file', blob, name);
      await fetch(`/policies/${name}`, { method: 'POST', headers: authHeaders, body: form });
    }
    loadPolicies();
  };

  const Dashboard = () => (
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <button onClick={loadStats}>Refresh Stats</button>
      <button onClick={loadEvents} style={{ marginLeft: '4px' }}>
        Refresh Events
      </button>
      <button onClick={loadPolicies} style={{ marginLeft: '4px' }}>
        Refresh Policies
      </button>
      <div style={{ marginTop: '8px', fontSize: '12px', color: '#555' }}>
        Dashboard transport: {streamStatus}
      </div>
      {stats && <pre style={{ background: '#eee', padding: '8px' }}>{JSON.stringify(stats, null, 2)}</pre>}
      {events.length > 0 && <pre style={{ background: '#eee', padding: '8px' }}>{JSON.stringify(events, null, 2)}</pre>}
      <PiiStatus count={redactedCount} />
      <Recommendations token={token} />
      <ConsentLedger token={token} />
      <Recall token={token} />
      <GraphView token={token} />
      <NodeSearch token={token} />
      <EdgeList token={token} />
      <LedgerHistory token={token} />
      <h3>Policies</h3>
      <ul>
        {policies.map((p) => (
          <li key={p.name}>
            <label>
              <input type="checkbox" checked={p.enabled} onChange={() => togglePolicy(p.name)} />
              <span onClick={() => setEditingPolicy(p.name)} style={{ cursor: 'pointer' }}>
                {p.name}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <PolicyEditor token={token} policy={editingPolicy} onSaved={loadPolicies} />
    </div>
  );

  if (!token) {
    return (
      <form onSubmit={login} style={{ padding: '20px' }}>
        <input placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} />
        <input
          placeholder="Password"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          style={{ marginLeft: '4px' }}
        />
        <button type="submit" style={{ marginLeft: '4px' }}>
          Login
        </button>
      </form>
    );
  }

  return (
    <BrowserRouter>
      <nav style={{ padding: '8px' }}>
        <Link to="/">Dashboard</Link>
        <Link to="/graph" style={{ marginLeft: '8px' }}>
          Graph
        </Link>
      </nav>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/graph" element={<GraphNetwork token={token} />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
