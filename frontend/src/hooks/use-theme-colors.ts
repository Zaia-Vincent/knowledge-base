import { useCallback, useEffect, useState } from 'react';

/**
 * Default CSS variable values for light and dark modes.
 * These match the oklch values defined in index.css.
 */

export interface ThemeColorSet {
    background: string;
    foreground: string;
    card: string;
    'card-foreground': string;
    primary: string;
    'primary-foreground': string;
    secondary: string;
    'secondary-foreground': string;
    muted: string;
    'muted-foreground': string;
    accent: string;
    'accent-foreground': string;
    destructive: string;
    border: string;
    input: string;
    ring: string;
}

export interface ThemeColors {
    light: ThemeColorSet;
    dark: ThemeColorSet;
}

const DEFAULT_LIGHT: ThemeColorSet = {
    background: '#ffffff',
    foreground: '#0a0a0a',
    card: '#ffffff',
    'card-foreground': '#0a0a0a',
    primary: '#171717',
    'primary-foreground': '#fafafa',
    secondary: '#f5f5f5',
    'secondary-foreground': '#171717',
    muted: '#f5f5f5',
    'muted-foreground': '#737373',
    accent: '#f5f5f5',
    'accent-foreground': '#171717',
    destructive: '#ef4444',
    border: '#e5e5e5',
    input: '#e5e5e5',
    ring: '#a3a3a3',
};

const DEFAULT_DARK: ThemeColorSet = {
    background: '#0a0a0a',
    foreground: '#fafafa',
    card: '#171717',
    'card-foreground': '#fafafa',
    primary: '#e5e5e5',
    'primary-foreground': '#171717',
    secondary: '#262626',
    'secondary-foreground': '#fafafa',
    muted: '#262626',
    'muted-foreground': '#a3a3a3',
    accent: '#262626',
    'accent-foreground': '#fafafa',
    destructive: '#dc2626',
    border: '#272727',
    input: '#272727',
    ring: '#737373',
};

export const DEFAULT_COLORS: ThemeColors = {
    light: DEFAULT_LIGHT,
    dark: DEFAULT_DARK,
};

const STORAGE_KEY = 'kb-theme-colors';

// CSS variable names to update
const CSS_VARS: (keyof ThemeColorSet)[] = [
    'background', 'foreground', 'card', 'card-foreground',
    'primary', 'primary-foreground', 'secondary', 'secondary-foreground',
    'muted', 'muted-foreground', 'accent', 'accent-foreground',
    'destructive', 'border', 'input', 'ring',
];

// Pretty label names for the UI
export const COLOR_LABELS: Record<keyof ThemeColorSet, string> = {
    background: 'Background',
    foreground: 'Foreground',
    card: 'Card',
    'card-foreground': 'Card Foreground',
    primary: 'Primary',
    'primary-foreground': 'Primary Foreground',
    secondary: 'Secondary',
    'secondary-foreground': 'Secondary Foreground',
    muted: 'Muted',
    'muted-foreground': 'Muted Foreground',
    accent: 'Accent',
    'accent-foreground': 'Accent Foreground',
    destructive: 'Destructive',
    border: 'Border',
    input: 'Input',
    ring: 'Ring',
};

function loadColors(): ThemeColors | null {
    try {
        const stored = localStorage.getItem(STORAGE_KEY);
        if (stored) return JSON.parse(stored);
    } catch { /* ignore parse errors */ }
    return null;
}

function applyColorsToDOM(colors: ThemeColors) {
    const root = document.documentElement;

    // Apply light mode colors to :root
    for (const key of CSS_VARS) {
        root.style.setProperty(`--color-${key}`, colors.light[key]);
    }

    // Apply dark mode via a style tag
    let styleEl = document.getElementById('kb-custom-dark-theme') as HTMLStyleElement | null;
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'kb-custom-dark-theme';
        document.head.appendChild(styleEl);
    }

    const darkVars = CSS_VARS.map(
        (key) => `  --color-${key}: ${colors.dark[key]};`
    ).join('\n');

    styleEl.textContent = `.dark {\n${darkVars}\n}`;
}

function removeCustomColors() {
    const root = document.documentElement;
    for (const key of CSS_VARS) {
        root.style.removeProperty(`--color-${key}`);
    }
    const styleEl = document.getElementById('kb-custom-dark-theme');
    if (styleEl) styleEl.remove();
}

export function useThemeColors() {
    const [colors, setColors] = useState<ThemeColors>(() => {
        return loadColors() ?? DEFAULT_COLORS;
    });
    const [hasCustom, setHasCustom] = useState(() => !!loadColors());

    // Apply colors on mount and when they change
    useEffect(() => {
        if (hasCustom) {
            applyColorsToDOM(colors);
        }
    }, [colors, hasCustom]);

    const updateColor = useCallback(
        (mode: 'light' | 'dark', key: keyof ThemeColorSet, value: string) => {
            setColors((prev) => ({
                ...prev,
                [mode]: { ...prev[mode], [key]: value },
            }));
            setHasCustom(true);
        },
        [],
    );

    const saveColors = useCallback(() => {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(colors));
        applyColorsToDOM(colors);
        setHasCustom(true);
    }, [colors]);

    const resetColors = useCallback(() => {
        localStorage.removeItem(STORAGE_KEY);
        removeCustomColors();
        setColors(DEFAULT_COLORS);
        setHasCustom(false);
    }, []);

    return {
        colors,
        hasCustom,
        updateColor,
        saveColors,
        resetColors,
    };
}
