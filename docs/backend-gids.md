# Backend Gids

Gedetailleerde configuratie- en ontwikkelgids voor de Python FastAPI backend van het Knowledge Base project.

## Technologie Stack

| Technologie | Versie | Doel |
|-------------|--------|------|
| **Python** | 3.12+ | Programmeertaal |
| **FastAPI** | 0.129+ | Async web framework |
| **SQLAlchemy** | 2.0+ | ORM met async support |
| **Alembic** | 1.18+ | Database migraties |
| **Pydantic** | v2 | Data validatie en serialisatie |
| **Pydantic Settings** | 2.12+ | Configuratie uit environment variabelen |

## Projectstructuur

```
backend/
├── app/
│   ├── main.py                    # FastAPI app factory
│   ├── config.py                  # Pydantic Settings configuratie
│   ├── domain/                    # Laag 1: Bedrijfsregels
│   │   ├── entities/              # Pure Python entiteiten
│   │   │   └── article.py         # Article dataclass
│   │   └── exceptions.py          # Domein-uitzonderingen
│   ├── application/               # Laag 2: Applicatielogica
│   │   ├── interfaces/            # Abstracte repositories (ports)
│   │   │   └── article_repository.py
│   │   ├── schemas/               # Pydantic DTOs
│   │   │   └── article.py
│   │   └── services/              # Use cases
│   │       └── article_service.py
│   ├── infrastructure/            # Laag 3: Frameworks & drivers
│   │   ├── database/
│   │   │   ├── base.py            # SQLAlchemy DeclarativeBase
│   │   │   ├── session.py         # Async DB sessie factory
│   │   │   ├── models/            # ORM modellen
│   │   │   └── repositories/      # Concrete repositories
│   │   └── dependencies.py        # FastAPI DI wiring
│   └── presentation/              # Laag 4: Interface adapters
│       └── api/
│           ├── router.py          # Top-level /api router
│           └── v1/
│               ├── router.py      # V1 router aggregatie
│               └── endpoints/     # Route handlers
│                   ├── health.py
│                   └── articles.py
└── tests/
    ├── unit/                      # Unit tests (fake repositories)
    └── integration/               # Integratie tests (httpx ASGI)
```

## Configuratie

### Environment Variabelen

De applicatie gebruikt **Pydantic Settings** om configuratie uit environment variabelen te laden:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_title: str = "Knowledge Base API"
    database_url: str = "sqlite:///./knowledge_base.db"
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = {"env_file": ".env"}
```

### `.env` Bestand

```env
DATABASE_URL=sqlite:///./knowledge_base.db
APP_ENV=development
APP_VERSION=0.1.0
CORS_ORIGINS=["http://localhost:5173"]
```

### Database Wisselen

Om PostgreSQL te gebruiken, wijzig de `DATABASE_URL`:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/knowledge_base
```

En installeer de async driver:

```bash
pip install asyncpg
```

De `session.py` converteert de URL automatisch naar het async equivalent.

## SQLAlchemy 2.0 Patronen

### Declarative Mapped Columns

SQLAlchemy 2.0 gebruikt `Mapped` en `mapped_column` voor type-veilige modellen:

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text

class ArticleModel(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
```

### Async Sessie Patroon

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Voorkomt lazy-loading fouten
)

async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### Entity ↔ Model Mapping

De clean architecture vereist expliciete mapping tussen domein-entiteiten en ORM modellen:

```python
class SQLAlchemyArticleRepository(ArticleRepository):

    def _to_entity(self, model: ArticleModel) -> Article:
        """ORM model → domein entiteit."""
        return Article(
            id=model.id,
            title=model.title,
            content=model.content,
        )

    def _to_model(self, entity: Article) -> ArticleModel:
        """Domein entiteit → ORM model."""
        return ArticleModel(
            title=entity.title,
            content=entity.content,
        )
```

## Dependency Injection

FastAPI's `Depends()` systeem wordt gebruikt als een lightweight DI container:

```python
# 1. DB sessie → Repository → Service (keten)
async def get_article_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ArticleService, None]:
    repository = SQLAlchemyArticleRepository(session)
    yield ArticleService(repository)

# 2. Gebruik in endpoint
@router.get("/{article_id}")
async def get_article(
    article_id: int,
    service: ArticleService = Depends(get_article_service),
):
    article = await service.get_article(article_id)
    return ArticleResponse.model_validate(article, from_attributes=True)
```

## Nieuwe Feature Toevoegen

### Stap-voor-stap:

1. **Domein-entiteit** maken in `domain/entities/`
2. **Repository interface** definiëren in `application/interfaces/`
3. **Pydantic schemas** maken in `application/schemas/`
4. **Service** (use case) maken in `application/services/`
5. **ORM model** maken in `infrastructure/database/models/`
6. **Concrete repository** implementeren in `infrastructure/database/repositories/`
7. **DI factory** toevoegen in `infrastructure/dependencies.py`
8. **Endpoints** maken in `presentation/api/v1/endpoints/`
9. **Router** registreren in `presentation/api/v1/router.py`

## Testen

### Unit Tests

Unit tests gebruiken **fake repositories** in plaats van de database:

```python
class FakeArticleRepository(ArticleRepository):
    def __init__(self):
        self._articles: dict[int, Article] = {}
        self._next_id = 1

    async def get_by_id(self, article_id: int) -> Article | None:
        return self._articles.get(article_id)

@pytest.fixture
def service() -> ArticleService:
    return ArticleService(FakeArticleRepository())

@pytest.mark.asyncio
async def test_create_article(service: ArticleService):
    data = ArticleCreate(title="Test", content="Inhoud")
    article = await service.create_article(data)
    assert article.id is not None
```

### Integratie Tests

Integratie tests gebruiken de ASGI transport van httpx:

```python
from httpx import ASGITransport, AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_health_check():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
```

### Tests Uitvoeren

```bash
# Alle tests
pytest tests/ -v

# Alleen unit tests
pytest tests/unit/ -v

# Alleen integratie tests
pytest tests/integration/ -v
```

## Commando's

| Commando | Beschrijving |
|----------|-------------|
| `uvicorn app.main:app --reload` | Start dev server op `http://localhost:8000` |
| `pytest tests/ -v` | Voer alle tests uit |
| `alembic upgrade head` | Voer migraties uit |
| `alembic revision --autogenerate -m "beschrijving"` | Nieuwe migratie genereren |
