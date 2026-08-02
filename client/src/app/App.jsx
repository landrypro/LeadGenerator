import { AppRouter } from './AppRouter'
import { AuthProvider } from '../features/auth/AuthContext'


export default function App({ invitationToken = '' }) {
  return <AuthProvider><AppRouter invitationToken={invitationToken} /></AuthProvider>
}
