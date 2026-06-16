/**
 * Firebase Storage upload service.
 * Files are stored at: tickets/{driverId}/{ticketId}/{filename}
 */
import { ref, uploadBytesResumable, getDownloadURL } from 'firebase/storage'
import { storage } from 'src/lib/firebase'

export interface UploadProgress {
  filename: string
  percent: number
}

/**
 * Upload a single file and return its download URL.
 * Calls onProgress(0–100) as the upload proceeds.
 */
export function uploadTicketFile(
  driverId: string,
  ticketId: string,
  file: File,
  onProgress?: (percent: number) => void
): Promise<string> {
  return new Promise((resolve, reject) => {
    const path = `tickets/${driverId}/${ticketId}/${file.name}`
    const storageRef = ref(storage, path)
    const task = uploadBytesResumable(storageRef, file)

    task.on(
      'state_changed',
      (snapshot) => {
        const pct = Math.round((snapshot.bytesTransferred / snapshot.totalBytes) * 100)
        onProgress?.(pct)
      },
      reject,
      async () => {
        try {
          const url = await getDownloadURL(task.snapshot.ref)
          resolve(url)
        } catch (err) {
          reject(err)
        }
      }
    )
  })
}

/**
 * Upload multiple files sequentially, reporting aggregate progress.
 * Returns an array of download URLs in the same order as the input files.
 */
export async function uploadTicketFiles(
  driverId: string,
  ticketId: string,
  files: File[],
  onProgress?: (progress: UploadProgress[]) => void
): Promise<string[]> {
  const progress: UploadProgress[] = files.map((f) => ({ filename: f.name, percent: 0 }))
  const urls: string[] = []

  for (let i = 0; i < files.length; i++) {
    const file = files[i]
    const url = await uploadTicketFile(driverId, ticketId, file, (pct) => {
      progress[i] = { filename: file.name, percent: pct }
      onProgress?.([...progress])
    })
    urls.push(url)
  }

  return urls
}
