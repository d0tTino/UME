import { useEffect, useState } from 'react';

export default function LedgerHistory({ token }) {
  const [events, setEvents] = useState([]);

  const load = async () => {
    const res = await fetch('/ledger/events?limit=20', {
      headers: { Authorization: 'Bearer ' + token },
    });
    if (res.ok) setEvents(await res.json());
  };

  useEffect(() => {
    if (token) load();
  }, [token]);

  if (!token) return null;

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Ledger History</h3>
      <button onClick={load}>Refresh</button>
      <ul>
        {events.map((e) => (
          <li key={e.offset}>
            {e.offset}: {e.event.event_type}
          </li>
        ))}
      </ul>
    </div>
  );
}
