// voice-interpreter.ts
// Calls the backend to interpret voice transcripts for different contexts.
// The backend uses the Anthropic API (ANTHROPIC_API_KEY is server-side only).
//
// Supported context types and their response shapes:
//
// 'production_log':
//   { entries: [{product_name:string, matched_product_id:string|null, quantity:number, confidence:number}],
//     unrecognized: string[], notes:string|null }
//
// 'incident':
//   { incident_type: 'near_miss'|'first_aid'|'recordable'|'property_damage'|'other',
//     location:string|null, people_involved:[{name:string, matched_id:string|null}],
//     description:string, immediate_actions:string|null, confidence:number }
//
// 'safety_observation':
//   { observation_type:'positive'|'concern'|'near_miss', location:string|null,
//     description:string, people_involved:[{name:string, matched_id:string|null}],
//     confidence:number }
//
// 'qc_fail_note':
//   { defect_description:string, disposition:'rework'|'scrap'|'accept'|null }
//
// 'inspection':
//   { overall_pass:boolean, issues:[{equipment:string|null, description:string}],
//     notes:string|null }

import apiClient from '@/lib/api-client'

export async function interpretVoice(
  context: string,
  transcript: string,
  availableProducts?: { id: string; name: string }[],
  availableEmployees?: { id: string; name: string }[]
): Promise<Record<string, unknown>> {
  const body: Record<string, unknown> = {
    context,
    transcript,
  }

  if (availableProducts !== undefined) {
    body.available_products = availableProducts
  }

  if (availableEmployees !== undefined) {
    body.available_employees = availableEmployees
  }

  try {
    const response = await apiClient.post('/operations-board/interpret', body)
    return response.data as Record<string, unknown>
  } catch (err) {
    if (err instanceof Error) {
      throw new Error(`Voice interpretation failed: ${err.message}`)
    }
    throw new Error('Voice interpretation failed: unknown error')
  }
}
