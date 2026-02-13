import { Palette, RotateCcw, Save, Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import {
    useThemeColors,
    COLOR_LABELS,
    type ThemeColorSet,
} from '@/hooks/use-theme-colors';

function ColorSwatch({
    label,
    value,
    onChange,
}: {
    label: string;
    value: string;
    onChange: (v: string) => void;
}) {
    return (
        <div className="flex items-center gap-3 group">
            <label className="relative cursor-pointer">
                <div
                    className="size-9 rounded-lg border border-border shadow-sm transition-all duration-200 group-hover:shadow-md group-hover:scale-105"
                    style={{ backgroundColor: value }}
                />
                <input
                    type="color"
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    className="absolute inset-0 size-full cursor-pointer opacity-0"
                />
            </label>
            <div className="flex flex-col">
                <span className="text-sm font-medium">{label}</span>
                <span className="text-xs text-muted-foreground font-mono uppercase">
                    {value}
                </span>
            </div>
        </div>
    );
}

function ColorSection({
    title,
    description,
    icon,
    mode,
    colors,
    onColorChange,
}: {
    title: string;
    description: string;
    icon: React.ReactNode;
    mode: 'light' | 'dark';
    colors: ThemeColorSet;
    onColorChange: (mode: 'light' | 'dark', key: keyof ThemeColorSet, value: string) => void;
}) {
    const keys = Object.keys(colors) as (keyof ThemeColorSet)[];

    return (
        <Card className="flex-1">
            <CardHeader className="pb-4">
                <div className="flex items-center gap-2">
                    {icon}
                    <CardTitle className="text-base">{title}</CardTitle>
                </div>
                <CardDescription>{description}</CardDescription>
            </CardHeader>
            <CardContent>
                <div className="grid gap-4 sm:grid-cols-2">
                    {keys.map((key) => (
                        <ColorSwatch
                            key={key}
                            label={COLOR_LABELS[key]}
                            value={colors[key]}
                            onChange={(v) => onColorChange(mode, key, v)}
                        />
                    ))}
                </div>
            </CardContent>
        </Card>
    );
}

export function ThemeColorsPage() {
    const { colors, hasCustom, updateColor, saveColors, resetColors } = useThemeColors();

    return (
        <div className="space-y-6 max-w-5xl">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="space-y-1">
                    <div className="flex items-center gap-2">
                        <Palette className="size-5 text-muted-foreground" />
                        <h1 className="text-2xl font-bold tracking-tight">Theme Colors</h1>
                    </div>
                    <p className="text-muted-foreground">
                        Customize the color palette for light and dark modes. Changes preview instantly.
                    </p>
                </div>
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={resetColors} disabled={!hasCustom}>
                        <RotateCcw className="size-3.5" />
                        Reset
                    </Button>
                    <Button size="sm" onClick={saveColors}>
                        <Save className="size-3.5" />
                        Save
                    </Button>
                </div>
            </div>

            <Separator />

            {/* Color editors */}
            <div className="grid gap-6 lg:grid-cols-2">
                <ColorSection
                    title="Light Mode"
                    description="Colors used when the light theme is active."
                    icon={<Sun className="size-4 text-amber-500" />}
                    mode="light"
                    colors={colors.light}
                    onColorChange={updateColor}
                />
                <ColorSection
                    title="Dark Mode"
                    description="Colors used when the dark theme is active."
                    icon={<Moon className="size-4 text-blue-400" />}
                    mode="dark"
                    colors={colors.dark}
                    onColorChange={updateColor}
                />
            </div>

            {/* Preview hint */}
            <Card className="bg-muted/50">
                <CardContent className="flex items-center gap-3 py-4">
                    <div className="flex size-8 items-center justify-center rounded-full bg-primary/10">
                        <Palette className="size-4 text-primary" />
                    </div>
                    <div className="text-sm">
                        <p className="font-medium">Live Preview</p>
                        <p className="text-muted-foreground">
                            Color changes apply instantly. Use the theme toggle in the top bar to
                            preview both modes. Click <strong>Save</strong> to persist your palette.
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
