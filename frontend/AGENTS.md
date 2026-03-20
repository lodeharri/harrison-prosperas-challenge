# Frontend - React SPA

## Overview
React single-page application for the Reto Prosperas async report processing system. Provides user authentication, report job creation, real-time status updates via WebSocket, and responsive UI with Tailwind CSS.

## Tech Stack
| Component | Technology |
|-----------|------------|
| Framework | React 19 + Vite |
| Language | TypeScript |
| Styling | Tailwind CSS 3.4 |
| HTTP Client | Axios 1.13 |
| Routing | React Router 7 |
| Container | Node 20 + Nginx Alpine |

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
│   │   └── Dashboard.tsx           # Main dashboard (form + job list)
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

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | http://localhost:8000 | Backend API base URL |
| `VITE_WS_URL` | ws://localhost:8000 | WebSocket URL |

## API Integration

### REST Endpoints (from backend)
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /auth/token | No | Login with user_id, returns JWT |
| POST | /jobs | JWT | Create report job |
| GET | /jobs | JWT | List user's jobs (paginated, 20/page) |
| GET | /jobs/{job_id} | JWT | Get job details |
| GET | /health | No | Health check |

### WebSocket Endpoint
| Path | Description |
|------|-------------|
| `/ws/jobs?user_id={id}&token={jwt}` | Real-time job status updates |

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

## Component Architecture

### Pages
| Component | Description |
|-----------|-------------|
| `Login` | User authentication form with user_id input |
| `Dashboard` | Main view with job form, list, toast notifications, and WS connection |

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

## Testing

> **Note:** Frontend tests are optional and not required for this project. The CI pipeline includes a `test-frontend` job that is configured to pass even if no tests exist.

```bash
# If you want to add tests (optional)
npm install --save-dev vitest @testing-library/react jsdom
```

## Commands
```bash
# Development
npm install
npm run dev

# Production build
npm run build

# Linting
npm run lint

# Testing (optional - not required)
npm test
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

### User Flow
1. **Login**: Enter user_id → POST `/auth/token` → Store JWT
2. **Create Job**: Fill form → POST `/jobs` → Add to list
3. **Real-time Updates**: WebSocket receives status changes → Update local job state
4. **View Results**: COMPLETED jobs show download button with `result_url`

## Dependencies
```json
{
  "axios": "^1.13.6",
  "react": "^19.2.4",
  "react-dom": "^19.2.4",
  "react-router-dom": "^7.13.1"
}
```

## Development Notes
- Uses React 19 with Vite for fast HMR
- TypeScript for type safety
- Tailwind CSS with custom primary color palette
- JWT decoding via base64 parsing (no external JWT library)
- WebSocket auto-reconnect handled by component lifecycle
