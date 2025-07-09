import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import GraphView from './GraphView';

function mockFetch(responses) {
  global.fetch = vi.fn((url) => {
    const res = responses[url] || { nodes: {}, edges: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(res) });
  });
}

describe('GraphView', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads graph structure', async () => {
    const data = { nodes: { n1: {} }, edges: [['n1', 'n2', 'e']] };
    mockFetch({ '/ledger/replay': data });
    render(<GraphView token="t" />);
    await waitFor(() => screen.getByText('n1 {}'));
    expect(screen.getByText('n1 {}')).toBeInTheDocument();
    expect(screen.getByText('n1 -[e]-> n2')).toBeInTheDocument();
  });
});
