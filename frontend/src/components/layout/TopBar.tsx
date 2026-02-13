import { Sun, Moon } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useTheme } from '@/hooks/use-theme';
import { Separator } from '@/components/ui/separator';

export function TopBar() {
    const { theme, toggleTheme } = useTheme();

    return (
        <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center border-b bg-background/80 backdrop-blur-lg supports-[backdrop-filter]:bg-background/60">
            <div className="flex flex-1 items-center justify-between px-4">
                {/* Left — breadcrumb / page info */}
                <div className="flex items-center gap-3">
                    <span className="text-sm font-medium text-muted-foreground">
                        Knowledge Base
                    </span>
                </div>

                {/* Right — actions */}
                <div className="flex items-center gap-2">
                    <Button
                        variant="ghost"
                        size="icon"
                        onClick={toggleTheme}
                        className="relative size-9 overflow-hidden"
                        aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
                    >
                        <Sun
                            className="absolute size-4 rotate-0 scale-100 transition-all duration-300 dark:-rotate-90 dark:scale-0"
                        />
                        <Moon
                            className="absolute size-4 rotate-90 scale-0 transition-all duration-300 dark:rotate-0 dark:scale-100"
                        />
                    </Button>
                </div>
            </div>
        </header>
    );
}
