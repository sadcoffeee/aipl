import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
// Fonts are bundled with the app (no font CDN needed): a display face for headings, a clean, friendly face for body text, and a monospace face for code.
import '@fontsource-variable/bricolage-grotesque'
import '@fontsource-variable/figtree'
import '@fontsource-variable/jetbrains-mono'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
