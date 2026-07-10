import { useEffect, useRef, useCallback } from "react";
import { useAuthStore } from "../store/authStore";

export function useWebSocket(path, onMessage) {
  const ws = useRef(null);
  const reconnectTimer = useRef(null);
  const { accessToken } = useAuthStore();

  useEffect(() => {
    if (!accessToken) return undefined;
    let active = true;

    const connect = () => {
      const base = import.meta.env.VITE_WS_URL || `ws://${window.location.host}`;
      const url = `${base}/${path}?token=${accessToken}`;
      ws.current = new WebSocket(url);
      ws.current.onmessage = (e) => onMessage(JSON.parse(e.data));
      // FIX BUG N°9 : la reconnexion était replanifiée même après le
      // démontage du composant (fuite + erreurs console). Elle n'est
      // désormais réarmée que tant que le hook est monté.
      ws.current.onclose = () => {
        if (active) reconnectTimer.current = setTimeout(connect, 3000);
      };
    };
    connect();

    return () => {
      active = false;
      clearTimeout(reconnectTimer.current);
      ws.current?.close();
    };
  }, [path, accessToken, onMessage]);

  const send = useCallback((data) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(data));
    }
  }, []);

  return { send };
}
