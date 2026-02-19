import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { HomePage } from '@/pages/HomePage';
import { SetupPage } from '@/pages/SetupPage';
import { ThemeColorsPage } from '@/pages/ThemeColorsPage';
import { ModelSettingsPage } from '@/pages/ModelSettingsPage';
import { ChatPage } from '@/pages/ChatPage';
import { OntologyPage } from '@/pages/OntologyPage';
import { QueryPage } from '@/pages/QueryPage';
import { ResourcesPage } from '@/pages/ResourcesPage';
import { DataSourcesPage } from '@/pages/DataSourcesPage';

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
                path: '/ontology',
                element: <OntologyPage />,
            },
            {
                path: '/query',
                element: <QueryPage />,
            },
            {
                path: '/data-sources',
                element: <DataSourcesPage />,
            },
            {
                path: '/resources',
                element: <ResourcesPage />,
            },
            {
                path: '/setup',
                element: <SetupPage />,
            },
            {
                path: '/setup/theme-colors',
                element: <ThemeColorsPage />,
            },
            {
                path: '/setup/model-settings',
                element: <ModelSettingsPage />,
            },
        ],
    },
]);
