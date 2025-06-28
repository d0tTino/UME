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

  const sendFeedback = async (id, feedback) => {
    await fetch('/recommendations/feedback', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ id, feedback }),
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
              onClick={() => sendFeedback(r.id, 'accepted')}
              style={{ marginLeft: '4px' }}
            >
              Accept
            </button>
            <button
              onClick={() => sendFeedback(r.id, 'rejected')}
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
