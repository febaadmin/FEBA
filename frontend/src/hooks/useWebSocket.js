import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "../store/authStore";

export function useWebSocket(path, onMessage) {
  const ws = useRef(null);
  const { accessToken } = useAuthStore();

  const connect = useCallback(() => {
    if (!accessToken) return;
    const base = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
    const url = `${base}/${path}?token=${accessToken}`;
    ws.current = new WebSocket(url);
    ws.current.onmessage = (e) => onMessage(JSON.parse(e.data));
    ws.current.onclose = () => setTimeout(connect, 3000);
  }, [path, accessToken, onMessage]);

  useEffect(() => {
    connect();
    return () => ws.current?.close();
  }, [connect]);

  const send = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}