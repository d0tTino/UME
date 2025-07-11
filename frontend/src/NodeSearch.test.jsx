import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import NodeSearch from './NodeSearch';

function mockFetch(responses) {
  global.fetch = vi.fn((url) => {
    const res = responses[url] || { nodes: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(res) });
  });
}

describe('NodeSearch', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('fetches nodes', async () => {
    mockFetch({ '/recall?query=q': { nodes: [{ id: 'n1', attributes: {} }] } });
    render(<NodeSearch token="t" />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'q' } });
    fireEvent.click(screen.getByText('Search'));
    await waitFor(() => screen.getByText('n1 {}'));
    expect(screen.getByText('n1 {}')).toBeInTheDocument();
  });
});
