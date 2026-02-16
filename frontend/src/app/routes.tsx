import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { HomePage } from '@/pages/HomePage';
import { SetupPage } from '@/pages/SetupPage';
import { ThemeColorsPage } from '@/pages/ThemeColorsPage';
import { ChatPage } from '@/pages/ChatPage';
import { FilesPage } from '@/pages/FilesPage';
import { FileDetailPage } from '@/pages/FileDetailPage';
import { OntologyPage } from '@/pages/OntologyPage';

export const router = createBrowserRouter([
    {
        element: <Layout />,
        children: [
            {
                path: '/',
                element: <HomePage />,
            },
            {
                path: '/chat',
                element: <ChatPage />,
            },
            {
                path: '/files',
                element: <FilesPage />,
            },
            {
                path: '/files/:id',
                element: <FileDetailPage />,
            },
            {
                path: '/ontology',
                element: <OntologyPage />,
            },
            {
                path: '/setup',
                element: <SetupPage />,
            },
            {
                path: '/setup/theme-colors',
                element: <ThemeColorsPage />,
            },
        ],
    },
]);
