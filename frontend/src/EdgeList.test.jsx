import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import EdgeList from './EdgeList';

function mockFetch(responses) {
  global.fetch = vi.fn((url) => {
    const res = responses[url] || { edges: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(res) });
  });
}

describe('EdgeList', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads edges', async () => {
    mockFetch({ '/ledger/replay': { edges: [['a', 'b', 'L']] } });
    render(<EdgeList token="t" />);
    await waitFor(() => screen.getByText('a -[L]-> b'));
    expect(screen.getByText('a -[L]-> b')).toBeInTheDocument();
  });
});
