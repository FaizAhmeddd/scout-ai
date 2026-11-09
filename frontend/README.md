# Frontend — Video Analysis Client

React (Vite) app for uploading football match videos, monitoring analysis jobs, and viewing detection/tracking results.

## Structure

```
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── common/        # generic UI building blocks (Button, Loader, Navbar)
│   │   ├── video/         # video upload + playback components
│   │   └── analysis/      # results/stats display components
│   ├── pages/             # route-level views (Home, Dashboard, VideoDetail)
│   ├── hooks/              # custom hooks (upload, polling analysis status)
│   ├── services/            # API client + endpoint wrappers
│   ├── context/             # global app state (React Context)
│   ├── utils/                # formatters, helpers
│   ├── App.jsx
│   └── main.jsx
├── index.html
├── package.json
└── vite.config.js
```

## Setup

```bash
npm install
npm run dev
```

The app expects the backend API at `VITE_API_BASE_URL` (see `.env.example`), default `http://localhost:8000/api/v1`.
