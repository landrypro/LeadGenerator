export function SessionLoadingPage({ message = 'Vérification de la session…' }) {
  return <main className="session-loading" aria-live="polite">
    <h1>{message}</h1>
  </main>
}
