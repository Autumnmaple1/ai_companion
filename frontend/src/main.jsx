import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
// 使用 v2 版本的 App（支持多会话管理）
import App from './AppV2.jsx'
import './AppV2.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
