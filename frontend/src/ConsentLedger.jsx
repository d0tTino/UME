import { useEffect, useState } from 'react';

export default function ConsentLedger({ token }) {
  const [entries, setEntries] = useState([]);
  const [userId, setUserId] = useState('');
  const [scope, setScope] = useState('');

  const headers = { Authorization: 'Bearer ' + token };

  const load = async () => {
    const res = await fetch('/consent', { headers });
    if (res.ok) setEntries(await res.json());
  };

  useEffect(() => {
    if (token) load();
  }, [token]);

  const add = async () => {
    await fetch('/consent', {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, scope }),
    });
    setUserId('');
    setScope('');
    load();
  };

  const remove = async (uid, sc) => {
    await fetch(`/consent?user_id=${encodeURIComponent(uid)}&scope=${encodeURIComponent(sc)}`, {
      method: 'DELETE',
      headers,
    });
    load();
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Consent Ledger</h3>
      <ul>
        {entries.map((e) => (
          <li key={e.user_id + e.scope}>
            {e.user_id} - {e.scope}
            <button onClick={() => remove(e.user_id, e.scope)} style={{ marginLeft: '4px' }}>
              Revoke
            </button>
          </li>
        ))}
      </ul>
      <div>
        <input placeholder="User ID" value={userId} onChange={(e) => setUserId(e.target.value)} />
        <input
          placeholder="Scope"
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          style={{ marginLeft: '4px' }}
        />
        <button onClick={add} style={{ marginLeft: '4px' }}>
          Add
        </button>
      </div>
    </div>
  );
}
