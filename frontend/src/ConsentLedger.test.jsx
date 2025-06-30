import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import ConsentLedger from './ConsentLedger';
import { vi, describe, it, expect, afterEach } from 'vitest';

function mockFetch(responses) {
  global.fetch = vi.fn((url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase();
    const key = method + ' ' + url;
    const response = responses[key] || responses[url] || {};
    return Promise.resolve({
      ok: true,
      json: () => Promise.resolve(response),
      text: () => Promise.resolve(JSON.stringify(response)),
    });
  });
}

describe('ConsentLedger', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });
  it('loads and displays entries', async () => {
    mockFetch({ '/consent': [{ user_id: 'u1', scope: 's1', timestamp: 1 }] });
    render(<ConsentLedger token="t" />);
    await waitFor(() => screen.getByText('u1 - s1'));
    expect(screen.getByText('u1 - s1')).toBeInTheDocument();
  });

  it('adds a new entry', async () => {
    const responses = {
      '/consent': [],
      'POST /consent': {},
    };
    mockFetch(responses);
    render(<ConsentLedger token="t" />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    fireEvent.change(screen.getByPlaceholderText('User ID'), { target: { value: 'u2' } });
    fireEvent.change(screen.getByPlaceholderText('Scope'), { target: { value: 's2' } });
    fireEvent.click(screen.getByText('Add'));
    expect(fetch).toHaveBeenCalledWith('/consent', expect.objectContaining({ method: 'POST' }));
  });
});
