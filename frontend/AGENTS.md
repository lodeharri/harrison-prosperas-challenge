# Frontend - React SPA

**Project:** Reto Prosperas - Report Job Processing System  
**Directory:** `frontend/`

## Context

This is the **Frontend Module** of the Reto Prosperas project. The full project context is documented in the root `AGENTS.md`.

### What is Reto Prosperas?
A system that allows users to create report jobs, processes them asynchronously via AWS SQS workers, and receives real-time notifications via WebSocket when jobs complete.

### Architecture Overview
```
Frontend (React SPA)
      │
      ▼ (REST + WebSocket)
Backend (FastAPI) ◄──────────────┐
      │                         │
      ▼ (SQS + DynamoDB)         │
Worker (SQS Consumer)           │
      │                         │
      ▼ (POST /internal/notify)─┘
```

## Scope

| Component | Responsibility |
|-----------|----------------|
| **Login** | Accept user_id, request JWT from API, store in localStorage |
| **Job Form** | Form to create report jobs (type, date_range, format) |
| **Job List** | Display user's jobs with status badges |
| **Job Details** | View individual job details |
| **WebSocket** | Real-time job status updates |
| **NOT** | Does NOT process jobs, does NOT store data - just calls the API |

## Complete Flow

```
1. User enters user_id → POST /auth/token → JWT stored in localStorage
         │
2. User fills job form (report_type, date_range, format) → POST /jobs
         │
3. API returns job_id → job appears in list with PENDING status
         │
4. Frontend connects to WebSocket: /ws/jobs?user_id={id}&token={jwt}
         │
5. Worker processes job (5-30s) → updates DynamoDB → POST /internal/notify
         │
6. API WebSocketManager broadcasts to frontend
         │
7. Frontend receives: {"type":"job_update", "data":{job_id, status, result_url}}
         │
8. UI updates: status badge changes, download button appears if COMPLETED
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | React 19 + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS 3.4 |
| HTTP Client | Axios 1.13 |
| Routing | React Router 7 |
| Container | Node 20 + Nginx Alpine |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | http://localhost:8000 | Backend API base URL |
| `VITE_WS_URL` | ws://localhost:8000 | WebSocket URL |

In production (via GitHub Actions):
- `VITE_API_URL` = API Gateway URL
- `VITE_WS_URL` = ALB URL (ws:// converted)

## API Integration

### REST Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/token | No | Login with user_id → JWT |
| POST | /jobs | JWT | Create report job |
| GET | /jobs | JWT | List user's jobs (paginated, 20/page) |
| GET | /jobs/{job_id} | JWT | Get job details |
| GET | /health | No | Health check |

### WebSocket Endpoint
```
/ws/jobs?user_id={id}&token={jwt}
```

### WebSocket Message Format
```typescript
{
  type: 'job_update',
  data: {
    job_id: string,
    status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED',
    result_url?: string,
    updated_at: string
  }
}
```

## If You Need To...

| Task | Go To |
|------|-------|
| Modify login page | `pages/Login.tsx` |
| Modify authentication logic | `hooks/useAuth.ts` |
| Modify job creation form | `components/jobs/JobForm.tsx` |
| Modify job list display | `components/jobs/JobList.tsx` |
| Modify job card/details | `components/jobs/JobCard.tsx` |
| Modify job status badge | `components/jobs/JobBadge.tsx` |
| Modify WebSocket logic | `hooks/useWebSocket.ts` |
| Modify API calls | `services/api.ts` |
| Modify TypeScript types | `types/index.ts` |
| Modify app routing | `App.tsx` |
| Modify styles | `index.css`, `tailwind.config.js` |
| Modify layout/header | `components/layout/Header.tsx`, `components/layout/Layout.tsx` |
| Modify notifications | `components/common/Toast.tsx` |

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── common/
│   │   │   └── Toast.tsx           # Toast notifications with auto-dismiss
│   │   ├── jobs/
│   │   │   ├── JobBadge.tsx        # Status badge (PENDING/PROCESSING/COMPLETED/FAILED)
│   │   │   ├── JobCard.tsx         # Individual job display card
│   │   │   ├── JobForm.tsx         # Report request form
│   │   │   └── JobList.tsx         # Jobs list with refresh
│   │   └── layout/
│   │       ├── Header.tsx          # App header with WS status indicator
│   │       └── Layout.tsx          # Main layout wrapper
│   ├── hooks/
│   │   ├── useAuth.ts              # JWT authentication logic
│   │   ├── useJobs.ts              # Job CRUD operations
│   │   └── useWebSocket.ts         # WebSocket connection management
│   ├── pages/
│   │   ├── Login.tsx               # User login page
│   │   ├── Dashboard.tsx           # Main dashboard (form + job list)
│   │   └── JobDetail.tsx           # Job detail page
│   ├── services/
│   │   └── api.ts                  # Axios client with JWT interceptors
│   ├── types/
│   │   └── index.ts                # TypeScript interfaces
│   ├── App.tsx                     # Root component with auth routing
│   ├── main.tsx                    # Entry point
│   └── index.css                   # Tailwind imports + custom styles
├── Dockerfile                      # Multi-stage build (Node 20 + Nginx)
├── nginx.conf                      # Nginx config with SPA routing + WS proxy
├── tailwind.config.js              # Tailwind configuration
├── .env.example                    # Environment variables template
└── package.json                    # Dependencies
```

## Component Architecture

### Pages
| Component | Description |
|-----------|-------------|
| `Login` | User authentication form with user_id input |
| `Dashboard` | Main view with job form, list, toast notifications, and WS connection |
| `JobDetail` | Individual job details view |

### Key Components
| Component | File | Purpose |
|-----------|------|---------|
| `JobBadge` | `components/jobs/` | Displays job status with emoji and color coding |
| `JobCard` | `components/jobs/` | Individual job display with download link |
| `JobForm` | `components/jobs/` | Report request form (type, date_range, format) |
| `JobList` | `components/jobs/` | Paginated job list with refresh button |
| `Toast` | `components/common/` | Notification popup with auto-dismiss |
| `Header` | `components/layout/` | App header with user info and WS status |
| `Layout` | `components/layout/` | Page wrapper with header |

### Job Status Display
| Status | Color | Emoji |
|--------|-------|-------|
| PENDING | Yellow | ⏳ |
| PROCESSING | Blue | 🔄 |
| COMPLETED | Green | ✅ |
| FAILED | Red | ❌ |

## Hooks

| Hook | Returns | Purpose |
|------|---------|---------|
| `useAuth` | `{ isAuthenticated, isLoading, error, login, logout }` | JWT token management and login |
| `useJobs` | `{ jobs, total, page, isLoading, error, fetchJobs, createJob, updateJobLocally }` | Job CRUD operations |
| `useWebSocket` | `{ isConnected, lastMessage, connect, disconnect }` | WebSocket lifecycle management |

## State Management

- **Local state** via React hooks (useState, useCallback)
- **No external state library** - simplicity over complexity
- **JWT token** stored in localStorage, managed via ApiService singleton
- **WebSocket messages** trigger local job list updates via `updateJobLocally`

## TypeScript Types

```typescript
type JobStatus = 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

interface Job {
  job_id: string;
  user_id: string;
  status: JobStatus;
  report_type: string;
  date_range: string;
  format: 'pdf' | 'csv' | 'excel';
  created_at: string;
  updated_at: string;
  result_url: string | null;
}

interface JobCreateRequest {
  report_type: string;
  date_range?: string;
  format?: 'pdf' | 'csv' | 'excel';
}

interface WebSocketMessage {
  type: 'job_update';
  data: {
    job_id: string;
    status: JobStatus;
    result_url?: string;
    updated_at: string;
  };
}
```

## Docker

- **Dockerfile**: Multi-stage build (Node 20 Alpine → Nginx Alpine)
- **Ports**: 3000 (host) → 80 (container)
- **Health check**: HTTP GET to `/health`
- **Features**: Gzip compression, static asset caching, security headers

### Nginx Features
- SPA routing (`try_files $uri $uri/ /index.html`)
- WebSocket proxy to backend (`/ws/` → `http://app:8000`)
- API proxy for production (`/api/` → `http://app:8000`)
- 1-year cache for static assets
- Security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)

## Commands

```bash
# Development
npm install
npm run dev

# Production build
npm run build

# Linting
npm run lint

# Docker (from project root)
docker compose up frontend
```

## Data Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   User      │────▶│   React UI   │────▶│  Axios API  │
│   Action    │     │  Components  │     │  Service    │
└─────────────┘     └──────────────┘     └──────┬──────┘
                          ▲                     │
                          │                     ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│  WebSocket  │────▶│  useWebSocket │     │  FastAPI    │
│  Server     │     │    Hook       │     │  Backend    │
└─────────────┘     └──────────────┘     └─────────────┘
       │                   │
       │                   ▼
       │            ┌──────────────┐
       └───────────▶│  Job List    │
                    │  Update      │
                    └──────────────┘
```

## Integration with Backend/Worker

The frontend connects to the backend but the actual job processing happens in the Worker:

```
Frontend                          Backend                          Worker
   │                                 │                                │
   ├── POST /auth/token ──────────▶ │                                │
   │                                 │                                │
   ├── POST /jobs ────────────────▶ │                                │
   │                                 ├── Save to DynamoDB           │
   │                                 ├── Send to SQS ──────────────▶ │
   │                                 │                                │ (processes 5-30s)
   │                                 │ ◀────────── /internal/notify ──┤
   │                                 │                                │
   │ ◀── WebSocket ─────────────────┤                                │
   │    {job_update, data: {...}}  │                                │
```

The frontend never talks directly to the Worker - all communication goes through the Backend API (REST + WebSocket).

## Development Notes

- Uses React 19 with Vite for fast HMR
- TypeScript for type safety
- Tailwind CSS with custom primary color palette
- JWT decoding via base64 parsing (no external JWT library)
- WebSocket auto-reconnect handled by component lifecycle
- Idempotency key header (`X-Idempotency-Key`) for job creation to prevent duplicates