import axios from 'axios';
import { io } from 'socket.io-client';

// Use environment variable if provided
// Otherwise, in production (non-localhost), route to the same origin so Nginx can proxy to the backend
let API_URL = import.meta.env.VITE_API_URL;
if (!API_URL) {
    if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
        API_URL = window.location.origin;
    } else {
        API_URL = 'http://localhost:5000';
    }
}

export const api = axios.create({
    baseURL: API_URL,
    timeout: 120000,  // 2 minutes - sandbox/LLM calls can be slow
    headers: {
        'Content-Type': 'application/json'
    }
});

export const socket = io(API_URL, {
    transports: ['websocket', 'polling'],
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000
});
