import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { HomePage } from '@/pages/HomePage';
import { SetupPage } from '@/pages/SetupPage';
import { ThemeColorsPage } from '@/pages/ThemeColorsPage';

export const router = createBrowserRouter([
    {
        element: <Layout />,
        children: [
            {
                path: '/',
                element: <HomePage />,
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
