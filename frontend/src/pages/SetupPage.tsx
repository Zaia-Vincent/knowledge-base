import { Link } from 'react-router-dom';
import { Palette, Settings, Cpu } from 'lucide-react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const setupModules = [
    {
        title: 'Theme Colors',
        description: 'Customize light and dark mode colors for the application.',
        icon: <Palette className="size-5" />,
        path: '/setup/theme-colors',
    },
    {
        title: 'LLM Models',
        description: 'Configure which AI model to use for each processing type.',
        icon: <Cpu className="size-5" />,
        path: '/setup/model-settings',
    },
];

export function SetupPage() {
    return (
        <div className="space-y-6">
            <div className="space-y-1">
                <div className="flex items-center gap-2">
                    <Settings className="size-5 text-muted-foreground" />
                    <h1 className="text-2xl font-bold tracking-tight">Setup</h1>
                </div>
                <p className="text-muted-foreground">
                    Configure and customize the application.
                </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {setupModules.map((module) => (
                    <Link key={module.path} to={module.path} className="group">
                        <Card className="h-full transition-all duration-200 hover:shadow-md hover:border-primary/30 group-hover:bg-accent/50">
                            <CardHeader className="pb-3">
                                <div className="flex items-center gap-3">
                                    <div className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                                        {module.icon}
                                    </div>
                                    <CardTitle className="text-base">{module.title}</CardTitle>
                                </div>
                            </CardHeader>
                            <CardContent>
                                <CardDescription>{module.description}</CardDescription>
                            </CardContent>
                        </Card>
                    </Link>
                ))}
            </div>
        </div>
    );
}
