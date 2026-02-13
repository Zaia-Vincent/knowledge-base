import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { useHealth } from '@/hooks/use-health';

export function HealthCard() {
    const { data, isLoading, error, refetch } = useHealth();

    return (
        <Card className="w-full max-w-md">
            <CardHeader>
                <CardTitle>Backend Status</CardTitle>
                <CardDescription>Real-time health check of the FastAPI backend</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {isLoading && (
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <div className="h-3 w-3 animate-pulse rounded-full bg-yellow-500" />
                        <span>Checking connection...</span>
                    </div>
                )}

                {error && (
                    <div className="flex items-center gap-2 text-destructive">
                        <div className="h-3 w-3 rounded-full bg-destructive" />
                        <span>{error}</span>
                    </div>
                )}

                {data && !isLoading && (
                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <div className="h-3 w-3 rounded-full bg-green-500" />
                            <span className="font-medium capitalize">{data.status}</span>
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
                            <span>Version:</span>
                            <span className="font-mono">{data.version}</span>
                            <span>Environment:</span>
                            <span className="font-mono">{data.environment}</span>
                        </div>
                    </div>
                )}

                <Button variant="outline" size="sm" onClick={refetch} disabled={isLoading}>
                    Refresh
                </Button>
            </CardContent>
        </Card>
    );
}
