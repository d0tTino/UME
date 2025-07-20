import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach, vi } from 'vitest';
import GraphExplorer from './GraphExplorer';

function mockFetch() {
  global.fetch = vi.fn(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ nodes: {}, edges: [] }) })
  );
}

describe('GraphExplorer', () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it('renders subcomponents', () => {
    mockFetch();
    render(<GraphExplorer token="t" />);
    expect(screen.getByText('Graph Explorer')).toBeInTheDocument();
    expect(screen.getByText('Node Search')).toBeInTheDocument();
    expect(screen.getByText('Graph')).toBeInTheDocument();
  });

  it('returns null without token', () => {
    const { container } = render(<GraphExplorer token="" />);
    expect(container.firstChild).toBeNull();
  });
});
