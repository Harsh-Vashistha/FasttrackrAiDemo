import axios from 'axios'
import type { Household, InsightsSummary, AudioInsight, UploadResult, ActionItem } from '../types'

const client = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

export const getHouseholds = () =>
  client.get<Household[]>('/households')

export const getHousehold = (id: number) =>
  client.get<Household>(`/households/${id}`)

export const updateHousehold = (id: number, data: Partial<Household>) =>
  client.put<Household>(`/households/${id}`, data)

export const getInsights = () =>
  client.get<InsightsSummary>('/insights/summary')

export const uploadExcel = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return client.post<UploadResult>('/upload/excel', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const uploadAudio = (file: File, householdId?: number) => {
  const formData = new FormData()
  formData.append('file', file)
  if (householdId !== undefined) {
    formData.append('household_id', String(householdId))
  }
  return client.post<AudioInsight>('/upload/audio', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getAudioInsights = (householdId: number) =>
  client.get<AudioInsight[]>(`/households/${householdId}/audio-insights`)

export const getActionItems = (householdId: number) =>
  client.get<ActionItem[]>(`/households/${householdId}/action-items`)

export const updateActionItemStatus = (householdId: number, itemId: number, status: 'pending' | 'completed') =>
  client.patch<ActionItem>(`/households/${householdId}/action-items/${itemId}`, { status })

export default client
