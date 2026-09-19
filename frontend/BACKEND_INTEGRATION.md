# Backend Integration Space

This project contains the frontend only. No backend server, database, AI model, or API implementation is included.

## Backend URL

Copy `.env.example` to `.env.local` and set:

```env
VITE_API_BASE_URL=http://localhost:8000/api
```

Use your real backend URL when deployed.

## Reserved API endpoints

- `POST /auth/login`
- `POST /auth/verify`
- `POST /auth/register`
- `POST /auth/forgot-password`
- `POST /auth/logout`
- `POST /chat`
- `GET /sessions`
- `POST /sessions`
- `GET /documents`
- `POST /documents`
- `GET /knowledge-base`
- `GET /agents`
- `GET /workflows`
- `GET /system/status`
- `GET /security`
- `GET /user/profile`

These are placeholders only. The frontend currently continues to use its existing demo/local behavior so the UI can be developed without a backend.

## Where to connect it later

- Authentication: `src/pages/Login.tsx`
- AI/chat: `src/services/aiService.ts`
- Session persistence: `src/hooks/useSessions.ts`
- Documents: `src/pages/Documents.tsx`
- Knowledge base: `src/pages/KnowledgeBase.tsx`
- Agents: `src/pages/Agents.tsx`
- Workflows: `src/pages/Workflows.tsx`
- Status/security/profile: corresponding pages under `src/pages/`
- Shared HTTP helper: `src/services/apiClient.ts`
- Endpoint configuration: `src/services/backendConfig.ts`

## Important

Do not put API secrets, database credentials, or model credentials in the Vite frontend. Only public configuration such as the backend base URL belongs in `VITE_*` variables.
