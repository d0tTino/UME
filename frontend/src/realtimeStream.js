const DEFAULT_RECONNECT_MS = 1000;
const MAX_RECONNECT_MS = 8000;

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

export function subscribeDashboardStream({ token, onDigest, onControl, onError, onReconnect }) {
  const state = { active: true, buffer: '', reconnectMs: DEFAULT_RECONNECT_MS, lastEventId: null };
  const decoder = new TextDecoder();

  const connect = async () => {
    while (state.active) {
      const params = new URLSearchParams();
      if (state.lastEventId !== null) params.set('lastEventId', state.lastEventId);
      const url = `/dashboard/stream${params.size ? `?${params}` : ''}`;

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
          parseSseChunk(state, decoder.decode(value, { stream: true }), (frame) => {
            if (frame.id !== undefined) state.lastEventId = frame.id;
            if (frame.event === 'dashboard_digest') onDigest(JSON.parse(frame.data));
            if (frame.event === 'control') onControl(JSON.parse(frame.data));
          });
        }
      } catch (error) {
        onError(error);
      }

      if (!state.active) break;
      onReconnect(state.reconnectMs);
      await new Promise((resolve) => setTimeout(resolve, state.reconnectMs));
      state.reconnectMs = Math.min(state.reconnectMs * 2, MAX_RECONNECT_MS);
    }
  };

  void connect();

  return () => {
    state.active = false;
  };
}
