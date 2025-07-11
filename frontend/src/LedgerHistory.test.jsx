import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import LedgerHistory from './LedgerHistory';

function mockFetch(responses) {
  global.fetch = vi.fn((url) => {
    const res = responses[url] || [];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(res) });
  });
}

describe('LedgerHistory', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads ledger events', async () => {
    mockFetch({ '/ledger/events?limit=20': [{ offset: 1, event: { event_type: 'CREATE_NODE' } }] });
    render(<LedgerHistory token="t" />);
    await waitFor(() => screen.getByText('1: CREATE_NODE'));
    expect(screen.getByText('1: CREATE_NODE')).toBeInTheDocument();
  });
});
