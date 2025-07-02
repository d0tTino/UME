import { useEffect, useState } from 'react';

export default function Recommendations({ token }) {
  const [recs, setRecs] = useState([]);

  useEffect(() => {
    if (!token) return;
    fetch('/recommendations', {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setRecs(data));
  }, [token]);

  const sendFeedback = async (id, accepted) => {
    const url = accepted ? '/feedback/accept' : '/feedback/reject';
    await fetch(url, {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ id }),
    });
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <h3>Recommendations</h3>
      <ul>
        {recs.map((r) => (
          <li key={r.id}>
            {r.action}
            <button
              onClick={() => sendFeedback(r.id, true)}
              style={{ marginLeft: '4px' }}
            >
              Accept
            </button>
            <button
              onClick={() => sendFeedback(r.id, false)}
              style={{ marginLeft: '4px' }}
            >
              Reject
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
