/**
 * FilesPage — Two-section layout for document management.
 *
 * Section 1: Upload & Processing — drag-and-drop upload with live processing queue
 * Section 2: Processed Files — accordion browser with type filter and detail panel
 */

import { useState } from 'react';
import { Upload, FolderOpen, RefreshCw } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useFiles } from '@/hooks/use-files';
import { FilesUploadSection } from '@/pages/FilesUploadSection';
import { FilesBrowserSection } from '@/pages/FilesBrowserSection';

/* ── Tab Navigation ──────────────────────────────────────────────── */

type TabId = 'upload' | 'browse';

const TABS: { id: TabId; label: string; icon: React.ReactNode; description: string }[] = [
    {
        id: 'upload',
        label: 'Upload & Processing',
        icon: <Upload className="size-4" />,
        description: 'Upload documents and monitor processing progress',
    },
    {
        id: 'browse',
        label: 'Processed Files',
        icon: <FolderOpen className="size-4" />,
        description: 'Browse, filter, and inspect processed documents',
    },
];

/* ── Page ─────────────────────────────────────────────────────────── */

export function FilesPage() {
    const { files, loading, error, uploading, uploadFiles, deleteFile, refetch } = useFiles();
    const [activeTab, setActiveTab] = useState<TabId>('upload');

    // Count files in processing (for badge)
    const processingCount = files.filter((f) =>
        ['pending', 'extracting_text', 'classifying', 'extracting_metadata'].includes(f.status),
    ).length;

    const completedCount = files.filter((f) => f.status === 'done' || f.status === 'error').length;

    return (
        <div className="h-full flex flex-col">
            {/* Header */}
            <div className="px-6 pt-6 pb-2 shrink-0">
                <div className="flex items-center justify-between mb-4">
                    <div>
                        <h1 className="text-2xl font-bold tracking-tight">Documents</h1>
                        <p className="text-sm text-muted-foreground mt-1">
                            Upload, classify, and extract metadata from documents
                        </p>
                    </div>
                    <Button
                        variant="ghost"
                        size="sm"
                        onClick={refetch}
                        disabled={loading}
                        className="gap-2"
                    >
                        <RefreshCw className={`size-4 ${loading ? 'animate-spin' : ''}`} />
                        Refresh
                    </Button>
                </div>

                {/* Tab bar */}
                <div className="flex items-center gap-1 border-b">
                    {TABS.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`
                                group relative flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors
                                ${activeTab === tab.id
                                    ? 'text-primary'
                                    : 'text-muted-foreground hover:text-foreground'
                                }
                            `}
                        >
                            {tab.icon}
                            {tab.label}

                            {/* Badge counter */}
                            {tab.id === 'upload' && processingCount > 0 && (
                                <span className="flex items-center justify-center size-5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold tabular-nums">
                                    {processingCount}
                                </span>
                            )}
                            {tab.id === 'browse' && completedCount > 0 && (
                                <span className="flex items-center justify-center min-w-[20px] h-5 px-1 rounded-full bg-muted text-muted-foreground text-[10px] font-bold tabular-nums">
                                    {completedCount}
                                </span>
                            )}

                            {/* Active indicator */}
                            {activeTab === tab.id && (
                                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-t-full" />
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Tab content */}
            <div className="flex-1 min-h-0 px-6 py-4">
                {activeTab === 'upload' ? (
                    <FilesUploadSection
                        files={files}
                        uploading={uploading}
                        loading={loading}
                        error={error}
                        onUpload={uploadFiles}
                        onRefetch={refetch}
                    />
                ) : (
                    <FilesBrowserSection
                        files={files}
                        onDelete={deleteFile}
                    />
                )}
            </div>
        </div>
    );
}
