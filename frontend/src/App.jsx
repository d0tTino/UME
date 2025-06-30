import { useState, useEffect } from 'react';
import PiiStatus from './PiiStatus';
import PolicyEditor from './PolicyEditor';
import Recommendations from './Recommendations';
import ConsentLedger from './ConsentLedger';

const POLICY_CONTENT = {
  'allow.rego': `package ume

# Allow an event only when no deny rules match

default allow = false

allow {
    not forbidden_node
    not admin_role_update
    not admin_edge
}
`,
  'deny_admin_role.rego': `package ume

# Deny updating a node role to "admin"

admin_role_update {
    input.event_type == "UPDATE_NODE_ATTRIBUTES"
    input.payload.attributes.role == "admin"
}
`,
  'deny_forbidden_node.rego': `package ume

# Deny creating a node with id "forbidden"

forbidden_node {
    input.event_type == "CREATE_NODE"
    input.payload.node_id == "forbidden"
}
`,
  'extra/deny_admin_edge.rego': `package ume

# Deny creating an edge from the admin node

admin_edge {
    input.event_type == "CREATE_EDGE"
    input.node_id == "admin"
}
`,
};

function App() {
  const [token, setToken] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [stats, setStats] = useState(null);
  const [events, setEvents] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [editingPolicy, setEditingPolicy] = useState('');

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

  useEffect(() => {
    if (token) {
      loadStats();
      loadEvents();
      loadPolicies();
    }
  }, [token]);

  const authHeaders = { Authorization: 'Bearer ' + token };

  const loadStats = async () => {
    const res = await fetch('/dashboard/stats', { headers: authHeaders });
    if (res.ok) setStats(await res.json());
  };

  const loadEvents = async () => {
    const res = await fetch('/dashboard/recent_events', { headers: authHeaders });
    if (res.ok) setEvents(await res.json());
  };

  const loadPolicies = async () => {
    const res = await fetch('/policies', { headers: authHeaders });
    if (res.ok) {
      const data = await res.json();
      const active = new Set(data.policies);
      setPolicies(
        Object.keys(POLICY_CONTENT).map((name) => ({ name, enabled: active.has(name) }))
      );
    }
  };

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

  const editPolicy = (name) => {
    setEditingPolicy(name);
  };

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
    <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
      <button onClick={loadStats}>Refresh Stats</button>
      <button onClick={loadEvents} style={{ marginLeft: '4px' }}>
        Refresh Events
      </button>
      <button onClick={loadPolicies} style={{ marginLeft: '4px' }}>
        Refresh Policies
      </button>
      {stats && (
        <pre style={{ background: '#eee', padding: '8px' }}>{JSON.stringify(stats, null, 2)}</pre>
      )}
      {events.length > 0 && (
        <pre style={{ background: '#eee', padding: '8px' }}>{JSON.stringify(events, null, 2)}</pre>
      )}
      <PiiStatus token={token} />
      <Recommendations token={token} />
      <ConsentLedger token={token} />
      <h3>Policies</h3>
      <ul>
        {policies.map((p) => (
          <li key={p.name}>
            <label>
              <input
                type="checkbox"
                checked={p.enabled}
                onChange={() => togglePolicy(p.name)}
              />
              <span onClick={() => editPolicy(p.name)} style={{ cursor: 'pointer' }}>
                {p.name}
              </span>
            </label>
          </li>
        ))}
      </ul>
      <PolicyEditor token={token} policy={editingPolicy} onSaved={loadPolicies} />
    </div>
  );
}

export default App;
