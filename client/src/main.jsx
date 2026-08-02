import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './app/App'
import { extractInvitationToken } from './features/invitations/invitationToken'
import './styles.css'

const invitationToken = extractInvitationToken(window)

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App invitationToken={invitationToken} />
  </StrictMode>,
)
