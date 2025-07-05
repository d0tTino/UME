import { render, screen, waitFor, cleanup } from '@testing-library/react';
import { vi, describe, it, expect, afterEach } from 'vitest';
import PiiStatus from './PiiStatus';

function mockFetch(data) {
  global.fetch = vi.fn(() =>
    Promise.resolve({
      ok: true,
      json: () => Promise.resolve(data),
    }),
  );
}

describe('PiiStatus', () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('polls and displays redaction count', async () => {
    const intervals = [];
    vi.spyOn(global, 'setInterval').mockImplementation((fn) => {
      intervals.push(fn);
      return 1;
    });
    mockFetch({ redacted: 3 });
    render(<PiiStatus token="t" />);
    await intervals[0]();
    await waitFor(() => screen.getByText('Redacted events: 3'));
    expect(fetch).toHaveBeenCalledWith('/pii/redactions', expect.any(Object));
  });

  it('does not poll without a token', () => {
    mockFetch({ redacted: 1 });
    render(<PiiStatus />);
    expect(fetch).not.toHaveBeenCalled();
  });
});
