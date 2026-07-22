import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router-dom'
import '@fontsource-variable/noto-sans-sc/index.css'
import '@fontsource-variable/nunito-sans/index.css'
import './index.css'
import { createAppRouter } from './router.tsx'

const router = createAppRouter()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
