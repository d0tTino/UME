import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import Recommendations from './Recommendations';

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
    return Promise.resolve({ ok, json: () => Promise.resolve(body) });
  });
}

describe('Recommendations', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads and displays recommendations', async () => {
    mockFetch({ '/recommendations': [{ id: 1, action: 'Act' }] });
    render(<Recommendations token="t" />);
    await waitFor(() => screen.getByText('Act'));
    expect(screen.getByText('Act')).toBeInTheDocument();
  });

  it('sends feedback on actions', async () => {
    const responses = {
      '/recommendations': [{ id: 1, action: 'Act' }],
      'POST /feedback/accept': {},
      'POST /feedback/reject': {},
    };
    mockFetch(responses);
    render(<Recommendations token="t" />);
    await waitFor(() => screen.getByText('Act'));
    fireEvent.click(screen.getByText('Accept'));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/feedback/accept',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
    fireEvent.click(screen.getByText('Reject'));
    await waitFor(() =>
      expect(fetch).toHaveBeenCalledWith(
        '/feedback/reject',
        expect.objectContaining({ method: 'POST' }),
      ),
    );
  });
});
