# HRMS Agent Frontend

React + TypeScript frontend for the HRMS Agent Chat system.

## Features

- ✅ Auto-authentication with hardcoded credentials
- ✅ JWT token management with automatic refresh
- ✅ Session management from URL parameters
- ✅ Real-time streaming chat (SSE)
- ✅ Chat history display
- ✅ Employee-specific conversation threads
- ✅ HRMS tool integration (leave, attendance, admin tools)
- ✅ Natural language interface for HRMS operations

## Setup

```bash
cd frontend
npm install
npm run dev
```

## Configuration

Set the API base URL in `.env`:

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

Or it will default to `http://localhost:8000/api/v1`.

## Usage

1. Open the frontend with a `sessionId` in the URL: `http://localhost:5173?sessionId=abc123`
2. The app will automatically:
   - Login with `hrms@recombd.com` / `12345678`
   - Fetch employee information from the session
   - Load chat history for that employee
   - Allow you to send messages

## Architecture

- **API Layer**: Axios client with JWT interceptors
- **Hooks**: Custom React hooks for auth, session, chat, and history
- **Components**: Reusable UI components with Tailwind CSS
- **State Management**: React Query for server state

## Build

```bash
npm run build
```

The built files will be in `dist/`.
