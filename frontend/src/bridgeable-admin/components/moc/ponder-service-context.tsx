/**
 * PonderServiceContext — the ponder's data plane, made swappable (Tenant
 * Ponder-Editor P2).
 *
 * The ponder components (overlay, artifacts, trigger composer, param
 * fields) are realm-clean UI; the ONE thing binding them to the admin app
 * was the moc-service import (adminApi). This context carries those calls:
 * the DEFAULT is the admin implementation — every existing admin mount is
 * byte-unchanged with no provider — and the tenant Bridgeable Map provides
 * the tenant implementations (apiClient, /api/v1/moc/*, company-scoped
 * server-side).
 *
 * `studioLinks` rides along: admin surfaces deep-link exhibits into Studio;
 * tenant surfaces don't (Studio is a platform door).
 */
import { createContext, useContext } from "react"

import {
  addTaskTrigger,
  deleteTrigger,
  getPonderDocumentPreview,
  getPonderScript,
  getTaskOfferPreview,
  listTriggerEvents,
  patchTrigger,
  publishTaskOffer,
  savePonderCaption,
  searchPonderUsers,
  setPonderWorkflowParam,
  type AddTriggerInput,
  type MoCTrigger,
  type MoCTriggerEvent,
  type PatchTriggerInput,
  type PonderScript,
  type PonderUserHit,
  type TaskOfferPreview,
} from "@/bridgeable-admin/services/moc-service"

export interface PonderService {
  getPonderScript: (taskId: string) => Promise<PonderScript>
  savePonderCaption: (
    taskId: string, beatKey: string, text: string | null,
  ) => Promise<Record<string, string>>
  getPonderDocumentPreview: (
    templateKey: string,
  ) => Promise<{ template_key: string; html: string }>
  addTaskTrigger: (taskId: string, input: AddTriggerInput) => Promise<MoCTrigger>
  patchTrigger: (triggerId: string, input: PatchTriggerInput) => Promise<MoCTrigger>
  deleteTrigger: (triggerId: string) => Promise<void>
  listTriggerEvents: (vertical?: string) => Promise<MoCTriggerEvent[]>
  setPonderWorkflowParam: (
    workflowId: string, stepKey: string, paramKey: string, value: unknown,
  ) => Promise<unknown>
  searchPonderUsers: (q: string) => Promise<PonderUserHit[]>
  /** Deep-link exhibits into Studio? Admin yes; tenant no. */
  studioLinks: boolean
  /** P3 — the deliberate publish boundary (ADMIN only; absent on the
   * tenant service, so the offer bar never renders there). */
  taskOfferPreview?: (taskId: string) => Promise<TaskOfferPreview>
  publishTaskOffer?: (
    taskId: string, patchNotes: string | null,
  ) => Promise<{ version: number; offers_created: number }>
}

/** The admin default — existing mounts work with no provider. */
export const adminPonderService: PonderService = {
  getPonderScript,
  savePonderCaption,
  getPonderDocumentPreview,
  addTaskTrigger,
  patchTrigger,
  deleteTrigger,
  listTriggerEvents,
  setPonderWorkflowParam,
  searchPonderUsers,
  studioLinks: true,
  taskOfferPreview: getTaskOfferPreview,
  publishTaskOffer,
}

export const PonderServiceContext = createContext<PonderService>(adminPonderService)

export function usePonderService(): PonderService {
  return useContext(PonderServiceContext)
}
