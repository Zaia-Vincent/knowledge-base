import { Link, useLocation } from 'react-router-dom';
import { useState } from 'react';
import {
    LayoutDashboard,
    Settings,
    Palette,
    ChevronDown,
    PanelLeftClose,
    PanelLeft,
    BookOpen,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';

interface SidebarProps {
    collapsed: boolean;
    onToggle: () => void;
}

interface NavItem {
    label: string;
    path: string;
    icon: React.ReactNode;
}

interface NavGroup {
    label: string;
    icon: React.ReactNode;
    children: NavItem[];
}

const navItems: NavItem[] = [
    { label: 'Dashboard', path: '/', icon: <LayoutDashboard className="size-4" /> },
];

const navGroups: NavGroup[] = [
    {
        label: 'Setup',
        icon: <Settings className="size-4" />,
        children: [
            { label: 'Theme Colors', path: '/setup/theme-colors', icon: <Palette className="size-4" /> },
        ],
    },
];

function NavLink({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
    const { pathname } = useLocation();
    const isActive = pathname === item.path;

    const link = (
        <Link
            to={item.path}
            className={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
                'hover:bg-accent hover:text-accent-foreground',
                isActive
                    ? 'bg-primary/10 text-primary dark:bg-primary/20'
                    : 'text-muted-foreground',
                collapsed && 'justify-center px-2',
            )}
        >
            {item.icon}
            {!collapsed && <span>{item.label}</span>}
        </Link>
    );

    if (collapsed) {
        return (
            <Tooltip delayDuration={0}>
                <TooltipTrigger asChild>{link}</TooltipTrigger>
                <TooltipContent side="right" sideOffset={8}>
                    {item.label}
                </TooltipContent>
            </Tooltip>
        );
    }

    return link;
}

function NavGroupSection({ group, collapsed }: { group: NavGroup; collapsed: boolean }) {
    const { pathname } = useLocation();
    const isChildActive = group.children.some((c) => pathname.startsWith(c.path));
    const [open, setOpen] = useState(isChildActive);

    if (collapsed) {
        return (
            <>
                {group.children.map((child) => (
                    <NavLink key={child.path} item={child} collapsed />
                ))}
            </>
        );
    }

    return (
        <div className="space-y-0.5">
            <button
                onClick={() => setOpen(!open)}
                className={cn(
                    'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200',
                    'hover:bg-accent hover:text-accent-foreground text-muted-foreground',
                    isChildActive && 'text-foreground',
                )}
            >
                {group.icon}
                <span className="flex-1 text-left">{group.label}</span>
                <ChevronDown
                    className={cn(
                        'size-3.5 transition-transform duration-200',
                        open && 'rotate-180',
                    )}
                />
            </button>
            {open && (
                <div className="ml-4 space-y-0.5 border-l border-border pl-2">
                    {group.children.map((child) => (
                        <NavLink key={child.path} item={child} collapsed={false} />
                    ))}
                </div>
            )}
        </div>
    );
}

export function AppSidebar({ collapsed, onToggle }: SidebarProps) {
    return (
        <TooltipProvider>
            <aside
                className={cn(
                    'flex h-screen flex-col border-r bg-sidebar text-sidebar-foreground transition-all duration-300 ease-in-out',
                    collapsed ? 'w-[60px]' : 'w-[240px]',
                )}
            >
                {/* Header */}
                <div className={cn(
                    'flex h-14 items-center border-b px-3',
                    collapsed ? 'justify-center' : 'gap-3',
                )}>
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground font-bold text-sm">
                        KB
                    </div>
                    {!collapsed && (
                        <span className="text-sm font-semibold tracking-tight truncate">
                            Knowledge Base
                        </span>
                    )}
                </div>

                {/* Navigation */}
                <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
                    {navItems.map((item) => (
                        <NavLink key={item.path} item={item} collapsed={collapsed} />
                    ))}

                    <Separator className="my-3" />

                    {navGroups.map((group) => (
                        <NavGroupSection key={group.label} group={group} collapsed={collapsed} />
                    ))}
                </nav>

                {/* Footer — toggle */}
                <div className="border-t p-2">
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={onToggle}
                        className={cn('w-full', collapsed && 'px-0')}
                    >
                        {collapsed ? (
                            <PanelLeft className="size-4" />
                        ) : (
                            <>
                                <PanelLeftClose className="size-4" />
                                <span className="ml-2 text-xs">Collapse</span>
                            </>
                        )}
                    </Button>
                </div>
            </aside>
        </TooltipProvider>
    );
}
