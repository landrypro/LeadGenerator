// Centralise le repli vers un message lisible quand une erreur ne fournit pas de détail.
export function toUserMessage(error, fallbackMessage = 'Une erreur inattendue est survenue.') {
  return error?.message || fallbackMessage
}
