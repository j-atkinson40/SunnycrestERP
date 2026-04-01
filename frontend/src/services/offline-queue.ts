// offline-queue.ts
// Manages offline submissions using raw IndexedDB.

export type QueueItemType =
  | 'production_log'
  | 'incident'
  | 'safety_observation'
  | 'qc_check'
  | 'inspection'
  | 'receiving'
  | 'driver_stop_status'
  | 'driver_exception'

export type QueueItemStatus = 'pending' | 'syncing' | 'synced' | 'failed'

export interface QueueItem {
  id: string
  type: QueueItemType
  payload: Record<string, unknown>
  created_at: string
  attempts: number
  last_error: string | null
  status: QueueItemStatus
}

const DB_NAME = 'bridgeable-ops-queue'
const STORE_NAME = 'queue'
const DB_VERSION = 1

function generateId(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return Date.now().toString()
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }

    request.onsuccess = (event) => {
      resolve((event.target as IDBOpenDBRequest).result)
    }

    request.onerror = (event) => {
      reject((event.target as IDBOpenDBRequest).error)
    }
  })
}

function getAuthHeader(): string {
  const token = localStorage.getItem('access_token')
  return token ? `Bearer ${token}` : ''
}

// Endpoint mapping
// - 'production_log'     → POST /api/v1/operations-board/production-log/bulk
// - 'incident'           → POST /api/v1/safety/incidents
// - 'safety_observation' → POST /api/v1/safety/observations
//                          NOTE: /safety/observations may not exist; falls back to
//                          POST /api/v1/safety/incidents with payload.type field
// - 'qc_check'           → PATCH /api/v1/operations-board/production-log/{entry_id}/qc
// - 'inspection'         → POST /api/v1/safety/inspections
// - 'receiving'          → POST /api/v1/purchase-orders/{po_id}/receive
function resolveEndpoint(item: QueueItem): { method: string; url: string } {
  const base = '/api/v1'
  switch (item.type) {
    case 'production_log':
      return { method: 'POST', url: `${base}/operations-board/production-log/bulk` }
    case 'incident':
      return { method: 'POST', url: `${base}/safety/incidents` }
    case 'safety_observation':
      return { method: 'POST', url: `${base}/safety/observations` }
    case 'qc_check': {
      const entryId = item.payload.entry_id as string
      return { method: 'PATCH', url: `${base}/operations-board/production-log/${entryId}/qc` }
    }
    case 'inspection':
      return { method: 'POST', url: `${base}/safety/inspections` }
    case 'receiving': {
      const poId = item.payload.po_id as string
      return { method: 'POST', url: `${base}/purchase-orders/${poId}/receive` }
    }
    case 'driver_stop_status': {
      const stopId = item.payload.stop_id as string
      return { method: 'PATCH', url: `${base}/driver/stops/${stopId}/status` }
    }
    case 'driver_exception': {
      const stopId = item.payload.stop_id as string
      return { method: 'POST', url: `${base}/driver/stops/${stopId}/exception` }
    }
  }
}

async function getAllItems(db: IDBDatabase): Promise<QueueItem[]> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const request = store.getAll()
    request.onsuccess = () => resolve(request.result as QueueItem[])
    request.onerror = () => reject(request.error)
  })
}

async function putItem(db: IDBDatabase, item: QueueItem): Promise<void> {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.put(item)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

async function enqueue(type: QueueItemType, payload: Record<string, unknown>): Promise<void> {
  const item: QueueItem = {
    id: generateId(),
    type,
    payload,
    created_at: new Date().toISOString(),
    attempts: 0,
    last_error: null,
    status: 'pending',
  }

  const db = await openDB()
  await putItem(db, item)
  db.close()

  window.dispatchEvent(new CustomEvent('queue-updated'))
}

async function processQueue(): Promise<void> {
  if (!navigator.onLine) return

  const db = await openDB()
  const allItems = await getAllItems(db)
  const workable = allItems.filter(
    (item) =>
      (item.status === 'pending' || item.status === 'failed') && item.attempts < 3
  )

  for (const item of workable) {
    // Mark as syncing
    item.status = 'syncing'
    await putItem(db, item)

    const { method, url } = resolveEndpoint(item)

    try {
      const response = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: getAuthHeader(),
        },
        body: JSON.stringify(item.payload),
      })

      if (response.ok) {
        item.status = 'synced'
        item.last_error = null
      } else if (response.status >= 400 && response.status < 500) {
        // Client error — do not retry
        item.status = 'failed'
        item.attempts += 1
        item.last_error = `HTTP ${response.status}: ${response.statusText}`
      } else {
        // Server error (5xx) — leave as pending to retry later
        item.status = 'pending'
        item.attempts += 1
        item.last_error = `HTTP ${response.status}: ${response.statusText}`
      }
    } catch (err) {
      // Network error — leave as pending to retry later
      item.status = 'pending'
      item.attempts += 1
      item.last_error = err instanceof Error ? err.message : 'Network error'
    }

    await putItem(db, item)
  }

  db.close()
  window.dispatchEvent(new CustomEvent('queue-updated'))
}

async function getPendingCount(): Promise<number> {
  const db = await openDB()
  const allItems = await getAllItems(db)
  db.close()
  return allItems.filter((item) => item.status === 'pending').length
}

function startBackgroundSync(): void {
  window.addEventListener('online', () => {
    processQueue()
  })

  setInterval(() => {
    if (navigator.onLine) {
      processQueue()
    }
  }, 30_000)
}

// Start background sync at module load time
startBackgroundSync()

const offlineQueue = {
  enqueue,
  processQueue,
  getPendingCount,
  startBackgroundSync,
}

export default offlineQueue
