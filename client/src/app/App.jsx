import { AppRouter } from './AppRouter'
import { AuthProvider } from '../features/auth/AuthContext'


export default function App() {
  return <AuthProvider><AppRouter /></AuthProvider>
}
