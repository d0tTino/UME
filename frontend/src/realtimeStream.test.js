import { afterEach, describe, expect, it, vi } from 'vitest';

import { appendReplayMarker, createDashboardStreamClient, toWebSocketUrl } from './realtimeStream';

describe('realtimeStream transport abstraction', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete global.fetch;
    delete global.WebSocket;
  });

  it('appends replay markers for SSE reconnects', () => {
    expect(appendReplayMarker('/dashboard/stream', '12')).toBe('/dashboard/stream?lastEventId=12');
  });

  it('delivers dashboard digest frames over SSE', async () => {
    const encoder = new TextEncoder();
    const frames = [
      'id: 7\nevent: dashboard_digest\ndata: {"cursor_offset":7,"stats":{"node_count":1,"edge_count":0,"vector_index_size":1},"recent_events":[],"redacted_count":0}\n\n',
    ];
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader() {
          let index = 0;
          return {
            read: vi.fn().mockImplementation(async () => {
              if (index >= frames.length) {
                return { done: true, value: undefined };
              }
              const value = encoder.encode(frames[index]);
              index += 1;
              return { done: false, value };
            }),
          };
        },
      },
    });

    const onDigest = vi.fn();
    const client = createDashboardStreamClient({ transport: 'sse' });
    client.subscribe({ token: 'token', onDigest, onControl: vi.fn(), onError: vi.fn(), onReconnect: vi.fn() });

    await vi.waitFor(() => expect(onDigest).toHaveBeenCalledWith(expect.objectContaining({ cursor_offset: 7 })));
  });

  it('builds websocket URLs and dispatches shared envelopes', async () => {
    const openSockets = [];
    class WebSocketStub {
      constructor(url, protocols) {
        this.url = url;
        this.protocols = protocols;
        openSockets.push(this);
        queueMicrotask(() => {
          this.onopen?.();
          this.onmessage?.({
            data: JSON.stringify({
              event: 'control',
              id: '9',
              data: JSON.stringify({ kind: 'heartbeat', cursor_offset: 9, dropped_events: 0 }),
            }),
          });
          this.onclose?.();
        });
      }

      close() {}
    }
    global.WebSocket = WebSocketStub;

    const onControl = vi.fn();
    const client = createDashboardStreamClient({ transport: 'websocket', webSocketEndpoint: '/dashboard/ws' });
    const unsubscribe = client.subscribe({ token: 'token', onDigest: vi.fn(), onControl, onError: vi.fn(), onReconnect: vi.fn() });

    await vi.waitFor(() => expect(onControl).toHaveBeenCalledWith(expect.objectContaining({ kind: 'heartbeat' })));
    expect(openSockets[0].url).toBe(toWebSocketUrl('/dashboard/ws', null));
    expect(openSockets[0].protocols).toEqual(['token']);
    unsubscribe();
  });
});
