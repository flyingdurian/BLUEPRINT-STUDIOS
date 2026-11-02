import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { persistenceBridge } from './sync/bridge'
import './styles.css'

const stopPersistence = persistenceBridge.start()
if (import.meta.hot) import.meta.hot.dispose(stopPersistence)

ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>)
