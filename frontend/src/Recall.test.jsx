import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import Recall from './Recall';

function mockFetch(responses) {
  global.fetch = vi.fn((url) => {
    const res = responses[url] || { nodes: [] };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(res) });
  });
}

describe('Recall', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('loads recall results', async () => {
    mockFetch({ '/recall?query=q': { nodes: [{ id: 'n1', attributes: {} }] } });
    render(<Recall token="t" />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'q' } });
    fireEvent.click(screen.getByText('Search'));
    await waitFor(() => screen.getByText('n1 {}'));
    expect(screen.getByText('n1 {}')).toBeInTheDocument();
  });
});
