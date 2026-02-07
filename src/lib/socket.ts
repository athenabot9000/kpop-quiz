import { io, Socket } from 'socket.io-client';

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io({
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 10,
      reconnectionDelay: 1000,
    });
  }
  return socket;
}

export function disconnectSocket(): void {
  if (socket) {
    socket.disconnect();
    socket = null;
  }
}

/**
 * Leave a room explicitly (cleanup between games).
 */
export function leaveRoom(roomCode: string): void {
  if (socket && socket.connected) {
    socket.emit('leave-room', { roomCode });
  }
}
