import axios from 'axios';
import { io } from 'socket.io-client';

// Use Railway backend in production, localhost for development
const API_URL = import.meta.env.VITE_BACKEND_URL || 'https://algolive-production.up.railway.app';

export const api = axios.create({
    baseURL: API_URL
});

export const socket = io(API_URL, {
    transports: ['websocket'],
    reconnection: true
});
