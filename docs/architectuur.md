# Architectuur Overzicht

Dit document beschrijft de architectuur van het Knowledge Base project. Het project volgt de **Clean Architecture** principes met een strikte scheiding van verantwoordelijkheden.

## Theoretische Achtergrond

Clean Architecture, geïntroduceerd door Robert C. Martin, is een softwarearchitectuur die **onafhankelijkheid** van frameworks, UI, databases en externe systemen bevordert. Het kernprincipe is de **Dependency Rule**: afhankelijkheden wijzen altijd naar **binnen** — de buitenste lagen mogen afhangen van binnenste lagen, maar nooit andersom.

```
┌──────────────────────────────────────────┐
│            Presentation Layer            │  ← FastAPI routes, middleware
│  ┌────────────────────────────────────┐  │
│  │        Infrastructure Layer        │  │  ← SQLAlchemy, repositories
│  │  ┌──────────────────────────────┐  │  │
│  │  │      Application Layer       │  │  │  ← Use cases, interfaces, DTOs
│  │  │  ┌────────────────────────┐  │  │  │
│  │  │  │     Domain Layer       │  │  │  │  ← Entities, business rules
│  │  │  └────────────────────────┘  │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

## De Vier Lagen

### 1. Domain Layer (`app/domain/`)

De kern van de applicatie. Bevat **pure Python objecten** zonder enige framework-afhankelijkheid.

**Componenten:**
- **Entities** (`entities/`): Bedrijfsentiteiten als dataclasses
- **Exceptions** (`exceptions.py`): Domein-specifieke fouttypen

**Voorbeeld:**
```python
from dataclasses import dataclass

@dataclass
class Article:
    title: str
    content: str
    id: int | None = None

    def update(self, title: str | None = None, content: str | None = None) -> None:
        if title is not None:
            self.title = title
        if content is not None:
            self.content = content
```

**Belangrijk:** De Domain Layer mag **nergens** van afhankelijk zijn — geen SQLAlchemy, geen FastAPI, geen Pydantic.

### 2. Application Layer (`app/application/`)

Bevat de **applicatielogica** (use cases) en definieert interfaces die de infrastructuur moet implementeren.

**Componenten:**
- **Interfaces** (`interfaces/`): Abstracte repository-klassen (ports)
- **Services** (`services/`): Use case implementaties
- **Schemas** (`schemas/`): Pydantic DTOs voor validatie van input/output

**Dependency Inversion Principle:**
```python
from abc import ABC, abstractmethod

class ArticleRepository(ABC):
    """Port — de applicatie definieert WAT nodig is."""

    @abstractmethod
    async def get_by_id(self, article_id: int) -> Article | None:
        ...

class ArticleService:
    """Use case — hangt af van de abstracte interface, niet de implementatie."""

    def __init__(self, repository: ArticleRepository):
        self._repository = repository
```

### 3. Infrastructure Layer (`app/infrastructure/`)

Implementeert de interfaces uit de Application Layer met concrete technologieën.

**Componenten:**
- **Database** (`database/`): SQLAlchemy sessie, ORM models, concrete repositories
- **Dependencies** (`dependencies.py`): FastAPI dependency injection wiring

**Voorbeeld Repository Implementatie:**
```python
class SQLAlchemyArticleRepository(ArticleRepository):
    """Implementeert de port met SQLAlchemy."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, article_id: int) -> Article | None:
        result = await self._session.get(ArticleModel, article_id)
        return self._to_entity(result) if result else None
```

### 4. Presentation Layer (`app/presentation/`)

De buitenste laag — verwerkt HTTP verzoeken en geeft antwoorden terug.

**Componenten:**
- **API routes** (`api/v1/endpoints/`): FastAPI route handlers
- **Routers** (`api/v1/router.py`): Route aggregatie met API versioning

## Dependency Injection (DI)

FastAPI's `Depends()` systeem wordt gebruikt om afhankelijkheden per request te injecteren:

```python
# infrastructure/dependencies.py
async def get_article_service(
    session: AsyncSession = Depends(get_db_session),
) -> AsyncGenerator[ArticleService, None]:
    repository = SQLAlchemyArticleRepository(session)
    yield ArticleService(repository)

# presentation/api/v1/endpoints/articles.py
@router.get("/{article_id}")
async def get_article(
    article_id: int,
    service: ArticleService = Depends(get_article_service),
):
    ...
```

## DRY Principes

Het project past DRY (Don't Repeat Yourself) toe op meerdere niveaus:

| Principe | Toepassing |
|----------|-----------|
| **Eén bron van waarheid** | Domein-entiteiten definiëren bedrijfsregels op één plek |
| **Abstracte interfaces** | Repository ports worden eenmalig gedefinieerd |
| **Centralisatie** | API client (frontend), DB sessie (backend) op één plek |
| **Barrel exports** | `__init__.py` bestanden hergroeperen publieke API's |

## Voordelen van deze Architectuur

1. **Testbaarheid**: Services testen met fake repositories (geen database nodig)
2. **Flexibiliteit**: Database wisselen door alleen de infrastructure laag aan te passen
3. **Onderhoudbaarheid**: Elke laag heeft een enkele verantwoordelijkheid
4. **Schaalbaarheid**: Nieuwe features toevoegen zonder bestaande code aan te raken
