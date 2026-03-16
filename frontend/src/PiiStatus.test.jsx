import { render, screen, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import PiiStatus from './PiiStatus';

describe('PiiStatus', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders redaction count', () => {
    render(<PiiStatus count={3} />);
    expect(screen.getByText('Redacted events: 3')).toBeTruthy();
  });

  it('defaults to zero-ish display via provided value', () => {
    render(<PiiStatus count={0} />);
    expect(screen.getByText('Redacted events: 0')).toBeTruthy();
  });
});
