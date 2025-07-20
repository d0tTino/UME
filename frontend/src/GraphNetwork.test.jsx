import { render, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import GraphNetwork from './GraphNetwork';
import { Network } from 'vis-network/standalone';

vi.mock('vis-network/standalone', () => ({ Network: vi.fn() }));

function mockFetch(response) {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve(response) })
  );
}

describe('GraphNetwork', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('fetches graph dump and renders network', async () => {
    const data = { nodes: { n1: {} }, edges: [['n1', 'n2', 'e']] };
    mockFetch(data);
    render(<GraphNetwork token="t" />);
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(Network).toHaveBeenCalled();
  });
});
