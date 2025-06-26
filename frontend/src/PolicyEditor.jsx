import { useEffect, useState } from 'react';

export default function PolicyEditor({ token, policy, onSaved }) {
  const [content, setContent] = useState('');

  useEffect(() => {
    if (!token || !policy) return;
    fetch(`/policies/${policy}`, {
      headers: { Authorization: 'Bearer ' + token },
    })
      .then((r) => (r.ok ? r.text() : ''))
      .then((t) => setContent(t));
  }, [token, policy]);

  if (!policy) return null;

  const save = async () => {
    const form = new FormData();
    form.append('file', new Blob([content], { type: 'text/plain' }), policy);
    await fetch(`/policies/${policy}`, {
      method: 'PUT',
      headers: { Authorization: 'Bearer ' + token },
      body: form,
    });
    if (onSaved) onSaved();
  };

  const validate = async () => {
    const res = await fetch('/policies/validate', {
      method: 'POST',
      headers: {
        Authorization: 'Bearer ' + token,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ content }),
    });
    if (res.ok) alert('Policy is valid');
    else alert('Policy has errors');
  };

  return (
    <div style={{ marginTop: '8px' }}>
      <h4>{policy}</h4>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        rows={10}
        cols={60}
      />
      <br />
      <button onClick={save}>Save</button>
      <button onClick={validate} style={{ marginLeft: '4px' }}>
        Validate
      </button>
    </div>
  );
}
