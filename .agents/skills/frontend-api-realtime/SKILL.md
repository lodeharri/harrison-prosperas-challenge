---
name: frontend-api-realtime
description: Implementation of the communication layer using Axios and native WebSockets.
---

# Instructions for Data Layer Implementation

1. **Axios Client**: Create a singleton instance in `src/services/api.ts`.
   - Implement interceptors for JWT injection (retrieved from secure storage).
   - Standardize error responses to trigger SweetAlert2 alerts automatically.
2. **WebSocket Manager**:
   - Implement a robust WebSocket service in `src/services/socket.ts` with auto-reconnect logic.
   - Use the Observer pattern to allow hooks to subscribe to specific message types.
3. **Hook Extraction**: 
   - All Axios calls must be wrapped in custom hooks (e.g., `useFetchJobs`).
   - Sockets must use a `useSocket` hook to manage subscription lifecycles.

## Success Criteria
- No Axios calls directly inside UI components.
- Error handling displays user-friendly SweetAlert2 modals for 4xx/5xx responses