import { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import { loadColors, applyColorsToDOM, fetchColorsFromApi } from '@/hooks/use-theme-colors';

export type Theme = 'light' | 'dark';

interface ThemeContextValue {
    theme: Theme;
    setTheme: (theme: Theme) => void;
    toggleTheme: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

const STORAGE_KEY = 'kb-theme';

function getInitialTheme(): Theme {
    if (typeof window === 'undefined') return 'light';
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') return stored;
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
    const [theme, setThemeState] = useState<Theme>(getInitialTheme);

    const applyTheme = useCallback((t: Theme) => {
        const root = document.documentElement;
        if (t === 'dark') {
            root.classList.add('dark');
        } else {
            root.classList.remove('dark');
        }
    }, []);

    useEffect(() => {
        applyTheme(theme);
    }, [theme, applyTheme]);

    // Apply saved theme colors on startup.
    // 1. Immediately apply from localStorage cache (avoids flash of default colors).
    // 2. Then fetch from backend API (source of truth) and refresh.
    useEffect(() => {
        // Instant: apply cached colors
        const cached = loadColors();
        if (cached) {
            applyColorsToDOM(cached);
        }

        // Async: fetch latest from backend and apply
        fetchColorsFromApi().then((result) => {
            if (result) {
                applyColorsToDOM(result.colors);
            }
        });
    }, []);

    const setTheme = useCallback((t: Theme) => {
        setThemeState(t);
        localStorage.setItem(STORAGE_KEY, t);
    }, []);

    const toggleTheme = useCallback(() => {
        setTheme(theme === 'dark' ? 'light' : 'dark');
    }, [theme, setTheme]);

    const value = useMemo(
        () => ({ theme, setTheme, toggleTheme }),
        [theme, setTheme, toggleTheme],
    );

    return (
        <ThemeContext.Provider value={value}>
            {children}
        </ThemeContext.Provider>
    );
}
