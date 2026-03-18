const DEFAULT_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 8000;
const DEFAULT_SSE_PATH = '/dashboard/stream';
const DEFAULT_WS_PATH = '/dashboard/ws';

function parseSseChunk(state, chunk, onFrame) {
  state.buffer += chunk;
  const frames = state.buffer.split('\n\n');
  state.buffer = frames.pop() || '';

  for (const rawFrame of frames) {
    const lines = rawFrame.split('\n');
    const frame = { event: 'message', data: '', id: undefined };
    for (const line of lines) {
      if (line.startsWith('event:')) frame.event = line.slice(6).trim();
      if (line.startsWith('data:')) frame.data += `${line.slice(5).trim()}\n`;
      if (line.startsWith('id:')) frame.id = line.slice(3).trim();
    }
    frame.data = frame.data.trim();
    if (frame.data) onFrame(frame);
  }
}

function createStreamState() {
  return {
    active: true,
    buffer: '',
    reconnectMs: DEFAULT_RECONNECT_MS,
    lastEventId: null,
  };
}

function appendReplayMarker(url, lastEventId, queryParam = 'lastEventId') {
  if (lastEventId === null || lastEventId === undefined) return url;
  const nextUrl = new URL(url, window.location.origin);
  nextUrl.searchParams.set(queryParam, lastEventId);
  return `${nextUrl.pathname}${nextUrl.search}${nextUrl.hash}`;
}

function dispatchEnvelope(frame, handlers, state) {
  if (frame.id !== undefined) state.lastEventId = frame.id;
  const payload = JSON.parse(frame.data);
  if (frame.event === 'dashboard_digest') handlers.onDigest(payload);
  if (frame.event === 'control') handlers.onControl(payload);
}

async function runSseSubscription({ token, state, handlers, endpoint = DEFAULT_SSE_PATH }) {
  const decoder = new TextDecoder();

  while (state.active) {
    const url = appendReplayMarker(endpoint, state.lastEventId);

    try {
      const response = await fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'text/event-stream',
        },
      });

      if (!response.ok || !response.body) {
        throw new Error(`dashboard_stream_http_${response.status}`);
      }

      state.reconnectMs = DEFAULT_RECONNECT_MS;
      const reader = response.body.getReader();

      while (state.active) {
        const { value, done } = await reader.read();
        if (done) break;
        parseSseChunk(state, decoder.decode(value, { stream: true }), (frame) =>
          dispatchEnvelope(frame, handlers, state),
        );
      }
    } catch (error) {
      handlers.onError(error);
    }

    if (!state.active) break;
    handlers.onReconnect(state.reconnectMs);
    await new Promise((resolve) => setTimeout(resolve, state.reconnectMs));
    state.reconnectMs = Math.min(state.reconnectMs * 2, MAX_RECONNECT_MS);
  }
}

function toWebSocketUrl(path, lastEventId) {
  const url = new URL(path, window.location.origin);
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
  if (lastEventId !== null && lastEventId !== undefined) {
    url.searchParams.set('lastEventId', lastEventId);
  }
  return url.toString();
}

async function runWebSocketSubscription({ token, state, handlers, endpoint = DEFAULT_WS_PATH }) {
  while (state.active) {
    let settled = false;

    try {
      await new Promise((resolve) => {
        const socket = new WebSocket(toWebSocketUrl(endpoint, state.lastEventId), [token]);

        socket.onopen = () => {
          settled = true;
          state.reconnectMs = DEFAULT_RECONNECT_MS;
        };

        socket.onmessage = (message) => {
          const frame = JSON.parse(message.data);
          dispatchEnvelope(frame, handlers, state);
        };

        socket.onerror = () => {
          handlers.onError(new Error('dashboard_stream_websocket_error'));
        };

        socket.onclose = () => {
          resolve();
        };

        if (!state.active) {
          socket.close();
          resolve();
        }
      });
    } catch (error) {
      handlers.onError(error);
    }

    if (!state.active) break;
    if (!settled) {
      handlers.onError(new Error('dashboard_stream_websocket_unavailable'));
    }
    handlers.onReconnect(state.reconnectMs);
    await new Promise((resolve) => setTimeout(resolve, state.reconnectMs));
    state.reconnectMs = Math.min(state.reconnectMs * 2, MAX_RECONNECT_MS);
  }
}

export function createDashboardStreamClient({
  transport = 'sse',
  sseEndpoint = DEFAULT_SSE_PATH,
  webSocketEndpoint = DEFAULT_WS_PATH,
} = {}) {
  return {
    subscribe({ token, onDigest, onControl, onError, onReconnect }) {
      const state = createStreamState();
      const handlers = {
        onDigest: onDigest ?? (() => {}),
        onControl: onControl ?? (() => {}),
        onError: onError ?? (() => {}),
        onReconnect: onReconnect ?? (() => {}),
      };

      if (transport === 'websocket') {
        void runWebSocketSubscription({ token, state, handlers, endpoint: webSocketEndpoint });
      } else {
        void runSseSubscription({ token, state, handlers, endpoint: sseEndpoint });
      }

      return () => {
        state.active = false;
      };
    },
  };
}

export function subscribeDashboardStream(options) {
  const { transport = 'sse', ...rest } = options;
  return createDashboardStreamClient({ transport }).subscribe(rest);
}

export { appendReplayMarker, dispatchEnvelope, parseSseChunk, toWebSocketUrl };
