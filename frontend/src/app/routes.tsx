import { createBrowserRouter } from 'react-router-dom';
import { Layout } from './Layout';
import { HomePage } from '@/pages/HomePage';
import { SetupPage } from '@/pages/SetupPage';
import { ThemeColorsPage } from '@/pages/ThemeColorsPage';
import { ChatPage } from '@/pages/ChatPage';

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
