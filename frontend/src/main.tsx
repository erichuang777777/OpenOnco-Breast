import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import './styles/app.css'

async function prepare() {
  // Enable mock API when VITE_MOCK=true (or running on port without a backend)
  if ((import.meta as unknown as Record<string, Record<string, string>>).env?.VITE_MOCK === 'true') {
    const { worker } = await import('./mock/browser')
    return worker.start({ onUnhandledRequest: 'bypass' })
  }
}

prepare().then(() => {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})
