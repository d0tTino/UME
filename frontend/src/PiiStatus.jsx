import { useEffect, useState } from 'react';

export default function PiiStatus({ token }) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!token) return;
    const id = setInterval(async () => {
      const res = await fetch('/pii/redactions', {
        headers: { Authorization: 'Bearer ' + token },
      });
      if (res.ok) {
        const data = await res.json();
        setCount(data.redacted);
      }
    }, 1000);
    return () => clearInterval(id);
  }, [token]);

  return <div>Redacted events: {count}</div>;
}
