export function toUserMessage(error, fallbackMessage = 'Une erreur inattendue est survenue.') {
  return error?.message || fallbackMessage
}
