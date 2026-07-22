import { Navigate, createBrowserRouter } from 'react-router-dom'
import type { RouteObject } from 'react-router-dom'
import App from './App'
import {
  courseLoader,
  courseMemoryLoader,
  coursesLoader,
  dailyRecordLoader,
  libraryNoteLoader,
  mistakesLoader,
  notesLoader,
  sectionNoteLoader,
  settingsLoader,
  statusLoader,
} from './routeData'

export const appRoutes: RouteObject[] = [
  {
    path: '/',
    element: <App />,
    hydrateFallbackElement: (
      <span className="route-progress route-progress--initial route-progress--visible" aria-hidden="true" />
    ),
    children: [
      { index: true, element: <Navigate to="/courses" replace /> },
      {
        path: 'courses',
        loader: coursesLoader,
        lazy: async () => ({ Component: (await import('./pages/CoursesPage')).CoursesPage }),
      },
      {
        path: 'example',
        lazy: async () => ({ Component: (await import('./pages/ExamplePage')).ExamplePage }),
      },
      {
        path: 'courses/:courseId',
        loader: courseLoader,
        lazy: async () => ({ Component: (await import('./pages/CourseDetailPage')).CourseDetailPage }),
      },
      {
        path: 'courses/:courseId/memory',
        loader: courseMemoryLoader,
        lazy: async () => ({ Component: (await import('./pages/CourseMemoryPage')).CourseMemoryPage }),
      },
      {
        path: 'daily-records/:recordId',
        loader: dailyRecordLoader,
        lazy: async () => ({ Component: (await import('./pages/DailyRecordPage')).DailyRecordPage }),
      },
      {
        path: 'daily-records/:recordId/note',
        loader: sectionNoteLoader,
        lazy: async () => ({ Component: (await import('./pages/SectionNotePage')).SectionNotePage }),
      },
      {
        path: 'mistakes',
        loader: mistakesLoader,
        lazy: async () => ({ Component: (await import('./pages/MistakesPage')).MistakesPage }),
      },
      { path: 'materials', element: <Navigate to="/settings?dialog=materials" replace /> },
      {
        path: 'notes',
        loader: notesLoader,
        shouldRevalidate: ({ currentUrl, nextUrl, defaultShouldRevalidate }) => (
          currentUrl.pathname === nextUrl.pathname ? false : defaultShouldRevalidate
        ),
        lazy: async () => ({ Component: (await import('./pages/NotesPage')).NotesPage }),
      },
      {
        path: 'notes/:sectionId',
        loader: libraryNoteLoader,
        lazy: async () => ({ Component: (await import('./pages/SectionNotePage')).SectionNotePage }),
      },
      {
        path: 'status',
        loader: statusLoader,
        lazy: async () => ({ Component: (await import('./pages/StatusPage')).StatusPage }),
      },
      {
        path: 'settings',
        loader: settingsLoader,
        lazy: async () => ({ Component: (await import('./pages/SettingsPage')).SettingsPage }),
      },
      { path: '*', element: <Navigate to="/courses" replace /> },
    ],
  },
]

export function createAppRouter() {
  return createBrowserRouter(appRoutes)
}
