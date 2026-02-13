import { HealthCard } from '@/features/health';

export function HomePage() {
    return (
        <div className="space-y-8">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
                <p className="text-muted-foreground">
                    Welcome to the Knowledge Base application.
                </p>
            </div>

            <section className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <HealthCard />
            </section>
        </div>
    );
}
