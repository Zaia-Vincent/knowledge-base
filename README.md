# Knowledge Base

Full-stack application with a **React** frontend and **FastAPI** backend, built with clean architecture principles.

## Tech Stack

| Layer      | Technology                                     |
|------------|-------------------------------------------------|
| Frontend   | React, TypeScript, Vite 7, Tailwind CSS v4, shadcn/ui |
| Backend    | Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic   |
| Database   | SQLite (default), swappable to PostgreSQL       |

## Quick Start

### Prerequisites

- **Node.js** ≥ 18
- **Python** ≥ 3.12

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173)

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for Swagger UI.

### Run Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

## Project Structure

```
knowledge-base/
├── frontend/              # React + TypeScript + Tailwind + shadcn
│   └── src/
│       ├── app/           # App shell, routing, providers
│       ├── components/ui/ # shadcn components
│       ├── features/      # Feature modules (domain-driven)
│       ├── hooks/         # Shared custom hooks
│       ├── lib/           # API client, utilities
│       ├── pages/         # Route pages
│       └── types/         # Shared TypeScript types
├── backend/               # Python + FastAPI + SQLAlchemy
│   ├── app/
│   │   ├── domain/        # Enterprise business rules (entities, exceptions)
│   │   ├── application/   # Use cases, interfaces, schemas
│   │   ├── infrastructure/# DB, repositories, DI
│   │   └── presentation/  # API endpoints, middleware
│   └── tests/
├── docs/                  # Documentation (Dutch)
└── .gitignore
```

## Architecture

This project follows **Clean Architecture** with dependency inversion:

```
Presentation → Application → Domain
                    ↑
              Infrastructure
```

- **Domain**: Pure business entities and exceptions — no framework dependencies
- **Application**: Use cases, abstract repository interfaces (ports), Pydantic DTOs
- **Infrastructure**: SQLAlchemy models, concrete repositories, FastAPI DI wiring
- **Presentation**: API endpoints, middleware, HTTP error mapping

## Documentation

Dutch documentation for developers is available in the [`docs/`](./docs) folder.
