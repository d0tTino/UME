import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import PolicyEditor from './PolicyEditor';

function mockFetch(responses) {
  global.fetch = vi.fn((url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase();
    const key = method + ' ' + url;
    const res = responses[key] ?? responses[url] ?? { ok: true, body: {} };
    const ok = res.ok !== undefined ? res.ok : true;
    const body = res.body !== undefined ? res.body : res;
    if (typeof body === 'string') {
      return Promise.resolve({ ok, text: () => Promise.resolve(body) });
    }
    return Promise.resolve({ ok, json: () => Promise.resolve(body), text: () => Promise.resolve(JSON.stringify(body)) });
  });
}

describe('PolicyEditor', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads and displays policy content', async () => {
    mockFetch({ '/policies/p.txt': 'hello' });
    render(<PolicyEditor token="t" policy="p.txt" />);
    await waitFor(() => screen.getByDisplayValue('hello'));
    expect(screen.getByRole('textbox').value).toBe('hello');
  });

  it('saves edited policy', async () => {
    const responses = {
      '/policies/p.txt': 'start',
      'PUT /policies/p.txt': {},
    };
    const onSaved = vi.fn();
    mockFetch(responses);
    render(<PolicyEditor token="t" policy="p.txt" onSaved={onSaved} />);
    await waitFor(() => screen.getByDisplayValue('start'));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'new' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/policies/p.txt',
        expect.objectContaining({ method: 'PUT' }),
      ),
    );
    expect(onSaved).toHaveBeenCalled();
  });

  it('validates policy content', async () => {
    const responses = {
      '/policies/p.txt': 'start',
      'POST /policies/validate': { ok: true, body: {} },
    };
    mockFetch(responses);
    global.alert = vi.fn();
    render(<PolicyEditor token="t" policy="p.txt" />);
    await waitFor(() => screen.getByDisplayValue('start'));
    fireEvent.click(screen.getByText('Validate'));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/policies/validate',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
    expect(global.alert).toHaveBeenCalledWith('Policy is valid');
  });
});
