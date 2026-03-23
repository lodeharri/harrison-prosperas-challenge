# Technical Documentation - Frontend SPA

## Overview
React 19 single-page application for the Reto Prosperas async report processing system. Provides authentication, report job management, and real-time status updates via WebSocket.

---

## 1. Frontend Architecture

### React SPA Structure
```
frontend/src/
├── components/          # UI Components (Atomic Design)
│   ├── common/         # Shared utilities
│   │   └── Toast.tsx   # Notification popup
│   ├── jobs/           # Job-specific components
│   │   ├── JobBadge.tsx    # Status display
│   │   ├── JobCard.tsx     # Individual job card
│   │   ├── JobForm.tsx     # Report request form
│   │   └── JobList.tsx     # Paginated job list
│   └── layout/         # Layout components
│       ├── Header.tsx      # App header + WS status
│       └── Layout.tsx     # Page wrapper
├── hooks/              # Business logic containers
│   ├── useAuth.ts      # JWT authentication
│   ├── useJobs.ts      # Job CRUD operations
│   └── useWebSocket.ts # WebSocket lifecycle
├── pages/              # Route-level components
│   ├── Login.tsx       # Authentication page
│   └── Dashboard.tsx   # Main application view
├── services/           # API clients (stateless)
│   └── api.ts          # Axios singleton + JWT
├── types/              # TypeScript interfaces
│   └── index.ts        # All shared types
├── App.tsx             # Root component + routing
├── main.tsx            # Entry point
└── index.css           # Tailwind + custom styles
```

### Component Hierarchy
```
App (BrowserRouter)
├── Login (route: /login)
│   └── AuthForm (inline)
│
└── Dashboard (route: /)
    └── Layout
        ├── Header (wsStatus, userId, logout)
        └── DashboardContent
            ├── JobForm (left column)
            │   └── Form inputs + submit
            │
            ├── JobList (right column)
            │   └── JobCard[] (repeating)
            │       └── JobBadge (status)
            │
            └── ToastContainer
                └── Toast[] (notifications)
```

---

## 2. State Management

### Architecture Pattern
- **No external state library** (React hooks + localStorage)
- **Local component state** via `useState`
- **Cross-component state** via custom hooks (`useAuth`, `useJobs`)
- **Token persistence** via `localStorage` + `ApiService` singleton

### Auth State (`useAuth.ts`)
```typescript
interface AuthState {
  isAuthenticated: boolean;  // Token exists in storage
  isLoading: boolean;         // Login request in progress
  error: string | null;      // Error message
  login(userId): Promise<boolean>;
  logout(): void;
}
```
- Token stored in `localStorage` key `token`
- Decoded JWT payload provides `user_id` (subject)

### Jobs State (`useJobs.ts`)
```typescript
interface JobsState {
  jobs: Job[];           // Current page items
  total: number;          // Total count across pages
  page: number;           // Current page number
  pageSize: number;       // Items per page (20)
  isLoading: boolean;     // Fetch/create in progress
  error: string | null;   // Error message
  setPage(n): void;       // Pagination
  fetchJobs(): void;      // Refresh list
  createJob(data): Promise<boolean>;
  updateJobLocally(jobId, updates): void;  // WebSocket trigger
}
```
- `updateJobLocally` allows real-time updates without refetch

### WebSocket State (`useWebSocket.ts`)
```typescript
interface WebSocketState {
  isConnected: boolean;            // Connection status
  lastMessage: WebSocketMessage | null;  // Latest received
  connect(userId): void;          // Establish connection
  disconnect(): void;              // Close connection
}
```
- Uses `useRef` to store WebSocket instance (survives re-renders)
- Message handler passed as callback to avoid dependency cycles

---

## 3. API Integration

### Axios Client Setup (`services/api.ts`)

#### Singleton Pattern
```typescript
class ApiService {
  private client: AxiosInstance;
  private token: string | null;

  constructor() {
    this.client = axios.create({
      baseURL: API_URL,
      headers: { 'Content-Type': 'application/json' },
    });

    // Request interceptor: attach JWT
    this.client.interceptors.request.use((config) => {
      if (this.token) {
        config.headers.Authorization = `Bearer ${this.token}`;
      }
      return config;
    });

    // Restore token from localStorage
    this.token = localStorage.getItem('token');
  }
}
```

#### Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/token` | No | Login with `user_id`, returns JWT |
| POST | `/jobs` | JWT | Create report job |
| GET | `/jobs` | JWT | List jobs (paginated, 20/page) |
| GET | `/jobs/{job_id}` | JWT | Get job details |
| GET | `/health` | No | Health check |

#### JWT Handling
- **Decode**: Base64 parse payload (`sub` = user_id)
- **Storage**: `localStorage.setItem('token', token)`
- **Removal**: `localStorage.removeItem('token')`

### Error Handling Strategy
```typescript
// Type-safe error extraction
const axiosError = err as { response?: { data?: { error?: { message?: string } } } };
const message = axiosError.response?.data?.error?.message || 'Default error';
```

---

## 4. WebSocket Connection

### Connection Flow
```
1. User logs in → JWT stored in localStorage
2. Dashboard mounts → useEffect calls connect(userId)
3. useWebSocket reads token from ApiService
4. Constructs URL: wss://<WS_URL>/ws/jobs?user_id={id}&token={jwt}
5. WebSocket opens → isConnected = true
6. Server sends job_update messages
7. Component unmounts → useEffect cleanup calls disconnect()
```

### Message Handler Integration
```typescript
// Dashboard.tsx
const handleWsMessage = useCallback((message: WebSocketMessage) => {
  if (message.type === 'job_update') {
    // Show toast notification
    addToast(`Job updated: ${message.data.status}`, ...);
    
    // Update job in local list
    updateJobLocally(message.data.job_id, {
      status: message.data.status,
      result_url: message.data.result_url,
    });
  }
}, [addToast, updateJobLocally]);

const { isConnected, connect, disconnect } = useWebSocket(handleWsMessage);
```

### WebSocket Message Format
```typescript
interface WebSocketMessage {
  type: 'job_update';
  data: {
    job_id: string;
    status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
    result_url?: string;  // Available on COMPLETED
    updated_at: string;
  };
}
```

### Reconnection Strategy
- **Manual reconnect**: User action triggers `connect()`
- **Auto-cleanup**: Unmount effect closes connection
- **Token refresh**: Reconnect uses current token from storage

---

## 5. Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND SPA                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────┐    ┌──────────────┐    ┌─────────────────────────┐   │
│  │  Login   │───▶│  ApiService  │───▶│  POST /auth/token       │   │
│  │  Form    │    │  (JWT Store) │    └─────────────────────────┘   │
│  └──────────┘    └──────────────┘              │                   │
│        │                                      │                    │
│        ▼                                      ▼                    │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      DASHBOARD                               │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐    │   │
│  │  │  JobForm    │  │  useJobs      │  │  useWebSocket  │    │   │
│  │  │  (Create)   │  │  (CRUD)       │  │  (Real-time)    │    │   │
│  │  └──────┬──────┘  └──────┬───────┘  └───────┬────────┘    │   │
│  │         │                │                   │              │   │
│  │         ▼                ▼                   ▼              │   │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐      │   │
│  │  │ POST /jobs  │  │ GET /jobs    │  │ WS Connection  │      │   │
│  │  └─────────────┘  └──────────────┘  └───────┬────────┘      │   │
│  └─────────────────────────────────────────────┼───────────────┘   │
│                                                  │                   │
└──────────────────────────────────────────────────┼───────────────────┘
                                                   │
                           ┌───────────────────────┼───────────────────┐
                           │                       ▼                   │
                           │              ┌────────────────┐          │
                           │              │  FastAPI WS    │          │
                           │              │  Manager        │          │
                           │              └───────┬────────┘          │
                           │                      │                   │
                           │              ┌────────┴────────┐          │
                           │              │                 │          │
                           │              ▼                 ▼          │
                           │         ┌─────────┐      ┌──────────┐     │
                           │         │ DynamoDB│◀─────│  Worker  │     │
                           │         └─────────┘      └────┬─────┘     │
                           │                              │            │
                           │                              ▼            │
                           │                         ┌────────┐        │
                           │                         │  SQS   │        │
                           │                         └────────┘        │
                           │                      BACKEND              │
                           └───────────────────────────────────────────┘
```

---

## 6. Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_URL` | `http://localhost:8000` | REST API base URL |
| `VITE_WS_URL` | `ws://localhost:8000` | WebSocket URL |

---

## 7. Tech Stack Summary

| Layer | Technology |
|-------|------------|
| Framework | React 19 + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS 3.4 |
| HTTP Client | Axios 1.13 |
| Routing | React Router 7 |
| Runtime | Node 20 + Nginx Alpine |

---

## 8. Key Implementation Details

### Token Persistence
```typescript
// api.ts - Singleton maintains token
class ApiService {
  private token: string | null;
  
  setToken(token: string | null) {
    this.token = token;
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }
}

// App.tsx - Hydrates auth state on load
const [isAuthenticated] = useState<boolean>(!!apiService.getToken());
```

### WebSocket Ref Pattern
```typescript
// useWebSocket.ts - Ref prevents reconnection loops
const wsRef = useRef<WebSocket | null>(null);
const onMessageRef = useRef(onMessage);  // Stable callback ref

// Update ref when callback changes
useEffect(() => {
  onMessageRef.current = onMessage;
}, [onMessage]);
```

### Local Job Updates
```typescript
// useJobs.ts - Update job without refetch
const updateJobLocally = useCallback((jobId: string, updates: Partial<Job>) => {
  setJobs(prev => prev.map(job => 
    job.job_id === jobId ? { ...job, ...updates } : job
  ));
}, []);
```
