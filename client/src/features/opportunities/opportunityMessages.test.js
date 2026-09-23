import { describe, expect, it } from 'vitest'

import { getOpportunityMessages, OPPORTUNITY_MESSAGES } from './opportunityMessages'

describe('opportunityMessages', () => {
  it('maintient les mêmes clés dans les catalogues fr-CA et en-CA', () => {
    const french = OPPORTUNITY_MESSAGES['fr-CA']
    const english = OPPORTUNITY_MESSAGES['en-CA']

    expect(Object.keys(english).sort()).toEqual(Object.keys(french).sort())
    expect(Object.keys(english.lossReasons).sort()).toEqual(Object.keys(french.lossReasons).sort())
    expect(Object.keys(english.reopenReasons).sort()).toEqual(Object.keys(french.reopenReasons).sort())
    expect(Object.keys(english.pipelineStages).sort()).toEqual(Object.keys(french.pipelineStages).sort())
  })

  it('utilise fr-CA comme repli pour une locale inconnue', () => {
    expect(getOpportunityMessages('unsupported')).toBe(OPPORTUNITY_MESSAGES['fr-CA'])
  })
})
