import axe from 'axe-core'


export async function axeViolations(container) {
  const results = await axe.run(container, {
    // jsdom ne calcule pas les couleurs réellement peintes. Le contraste est
    // contrôlé dans la matrice manuelle obligatoire de 2.3.5-E.
    rules: { 'color-contrast': { enabled: false } },
  })
  return results.violations
}


export function formatViolations(violations) {
  return violations.map((violation) => ({
    id: violation.id,
    impact: violation.impact,
    nodes: violation.nodes.map((node) => node.target.join(' ')),
  }))
}
