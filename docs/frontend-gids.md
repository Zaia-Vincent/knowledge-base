# Frontend Gids

Gedetailleerde configuratie- en ontwikkelgids voor de frontend component van het Knowledge Base project.

## Technologie Stack

| Technologie | Versie | Doel |
|-------------|--------|------|
| **React** | 19.x | UI framework |
| **TypeScript** | 5.x | Type-veiligheid |
| **Vite** | 7.x | Build tool en dev server |
| **Tailwind CSS** | v4 | Utility-first CSS framework |
| **shadcn/ui** | latest | Herbruikbare UI componenten |
| **React Router** | v7 | Client-side routing |

## Mappenstructuur

```
frontend/src/
├── app/                    # Applicatie shell
│   ├── Layout.tsx          # Hoofdlayout met navigatie
│   └── routes.tsx          # React Router configuratie
├── components/             # Gedeelde UI componenten
│   └── ui/                 # shadcn/ui componenten (auto-gegenereerd)
│       ├── button.tsx
│       └── card.tsx
├── features/               # Feature modules (domein-gedreven)
│   └── health/             # Voorbeeld feature
│       ├── components/     # Feature-specifieke componenten
│       │   └── HealthCard.tsx
│       └── index.ts        # Barrel export
├── hooks/                  # Gedeelde custom hooks
│   └── use-health.ts       # Backend health check hook
├── lib/                    # Utilities en helpers
│   ├── api-client.ts       # Gecentraliseerde API client
│   └── utils.ts            # shadcn utility (cn functie)
├── pages/                  # Route pagina's
│   └── HomePage.tsx
├── types/                  # Gedeelde TypeScript types
│   └── api.types.ts
├── index.css               # Tailwind CSS v4 configuratie
└── main.tsx                # Entry point
```

## Tailwind CSS v4

Tailwind CSS v4 gebruikt een **CSS-first** configuratie — geen `tailwind.config.js` meer nodig.

### Configuratie

De configuratie zit direct in `src/index.css`:

```css
@import "tailwindcss";
@import "tw-animate-css";
@import "shadcn/tailwind.css";

@custom-variant dark (&:is(.dark *));

@theme inline {
  --radius-sm: calc(var(--radius) - 4px);
  --color-background: var(--background);
  --font-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
  /* ... meer design tokens */
}
```

### Vite Plugin

In `vite.config.ts` wordt Tailwind geïntegreerd via het Vite plugin:

```typescript
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```

## shadcn/ui Componenten

shadcn/ui levert **kopieerbare** componenten — geen npm package, maar broncode die je bezit en aanpast.

### Componenten Toevoegen

```bash
npx shadcn@latest add dialog
npx shadcn@latest add table
npx shadcn@latest add form
```

### Gebruik in Code

```tsx
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

function MyComponent() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Mijn Kaart</CardTitle>
      </CardHeader>
      <CardContent>
        <Button variant="outline">Klik hier</Button>
      </CardContent>
    </Card>
  );
}
```

## API Client

De gecentraliseerde API client in `lib/api-client.ts` biedt een **DRY** interface voor alle backend-communicatie:

```typescript
import { apiClient } from '@/lib/api-client';

// GET request
const articles = await apiClient.get<Article[]>('/articles');

// POST request
const newArticle = await apiClient.post<Article>('/articles', {
  title: 'Nieuw Artikel',
  content: 'Inhoud hier...',
});

// Error handling
import { ApiError } from '@/lib/api-client';

try {
  await apiClient.get('/articles/999');
} catch (err) {
  if (err instanceof ApiError) {
    console.error(`Server fout: ${err.status}`);
  }
}
```

## Feature Module Patroon

Nieuwe features worden als zelfstandige modules toegevoegd:

```
features/
└── articles/
    ├── api/              # API calls voor deze feature
    │   └── article-api.ts
    ├── components/       # Feature-specifieke componenten
    │   ├── ArticleList.tsx
    │   └── ArticleForm.tsx
    ├── hooks/            # Feature-specifieke hooks
    │   └── use-articles.ts
    ├── types/            # Feature-specifieke types
    │   └── article.types.ts
    └── index.ts          # Barrel export
```

### Stappen om een Feature toe te voegen:

1. Maak de mappenstructuur aan
2. Definieer de types
3. Maak de API calls
4. Bouw de custom hooks
5. Implementeer de componenten
6. Voeg een route toe in `routes.tsx`

## Path Aliases

Het project gebruikt `@/` als alias voor de `src/` map:

```typescript
// In plaats van:
import { Button } from '../../../components/ui/button';

// Gebruik:
import { Button } from '@/components/ui/button';
```

Geconfigureerd in `tsconfig.json` en `vite.config.ts`.

## API Proxy

De Vite dev server proxied `/api` verzoeken naar de FastAPI backend:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/api': {
      target: 'http://localhost:8000',
      changeOrigin: true,
    },
  },
}
```

Dit voorkomt CORS-problemen tijdens lokale ontwikkeling.

## Commando's

| Commando | Beschrijving |
|----------|-------------|
| `npm run dev` | Start dev server op `http://localhost:5173` |
| `npm run build` | Bouw productie-bundle |
| `npm run preview` | Preview productie-build lokaal |
