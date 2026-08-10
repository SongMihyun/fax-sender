import type { ProcessedPdf } from "../types";

type DirectoryHandle = {
  name: string;
  queryPermission?: (descriptor: { mode: "readwrite" }) => Promise<PermissionState>;
  requestPermission?: (descriptor: { mode: "readwrite" }) => Promise<PermissionState>;
  getFileHandle: (name: string, options: { create: boolean }) => Promise<{
    createWritable: () => Promise<{
      write: (data: Blob) => Promise<void>;
      close: () => Promise<void>;
    }>;
  }>;
};

type SaveFileHandle = {
  createWritable: () => Promise<{
    write: (data: Blob) => Promise<void>;
    close: () => Promise<void>;
  }>;
};

type WindowWithDirectoryPicker = Window & {
  showDirectoryPicker?: (options?: { startIn?: DirectoryHandle | "desktop" | "documents" | "downloads" }) => Promise<DirectoryHandle>;
  showSaveFilePicker?: (options: {
    suggestedName: string;
    types: Array<{
      description: string;
      accept: Record<string, string[]>;
    }>;
  }) => Promise<SaveFileHandle>;
};

const dbName = "faxsender-file-handles";
const storeName = "handles";
const outputDirectoryKey = "output-directory";

function createPdfBlob(bytes: Uint8Array): Blob {
  const buffer = new ArrayBuffer(bytes.byteLength);
  new Uint8Array(buffer).set(bytes);
  return new Blob([buffer], { type: "application/pdf" });
}

function triggerDownload(result: ProcessedPdf) {
  const link = document.createElement("a");
  link.href = result.blobUrl;
  link.download = result.filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
}

function openHandleDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(dbName, 1);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(storeName);
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function getStoredDirectoryHandle(): Promise<DirectoryHandle | null> {
  try {
    const db = await openHandleDb();
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(storeName, "readonly");
      const request = tx.objectStore(storeName).get(outputDirectoryKey);
      request.onsuccess = () => resolve((request.result as DirectoryHandle | undefined) ?? null);
      request.onerror = () => reject(request.error);
      tx.oncomplete = () => db.close();
    });
  } catch {
    return null;
  }
}

async function storeDirectoryHandle(handle: DirectoryHandle) {
  try {
    const db = await openHandleDb();
    await new Promise<void>((resolve, reject) => {
      const tx = db.transaction(storeName, "readwrite");
      tx.objectStore(storeName).put(handle, outputDirectoryKey);
      tx.oncomplete = () => {
        db.close();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    });
  } catch {
    // Some browsers do not allow persisting file handles. Saving still works for this click.
  }
}

async function ensureWritePermission(handle: DirectoryHandle): Promise<boolean> {
  if (handle.queryPermission) {
    const current = await handle.queryPermission({ mode: "readwrite" });
    if (current === "granted") return true;
  }

  if (!handle.requestPermission) return true;
  return (await handle.requestPermission({ mode: "readwrite" })) === "granted";
}

async function pickDirectory(startIn?: DirectoryHandle): Promise<DirectoryHandle | null> {
  const picker = (window as WindowWithDirectoryPicker).showDirectoryPicker;
  if (!picker) return null;
  const handle = await picker(startIn ? { startIn } : undefined);
  await storeDirectoryHandle(handle);
  return handle;
}

async function writePdfToDirectory(handle: DirectoryHandle, result: ProcessedPdf) {
  const fileHandle = await handle.getFileHandle(result.filename, { create: true });
  const writable = await fileHandle.createWritable();
  await writable.write(createPdfBlob(result.bytes));
  await writable.close();
}

async function savePdfWithFilePicker(result: ProcessedPdf): Promise<string | null> {
  const picker = (window as WindowWithDirectoryPicker).showSaveFilePicker;
  if (!picker) return null;

  const fileHandle = await picker({
    suggestedName: result.filename,
    types: [
      {
        description: "PDF 파일",
        accept: { "application/pdf": [".pdf"] },
      },
    ],
  });
  const writable = await fileHandle.createWritable();
  await writable.write(createPdfBlob(result.bytes));
  await writable.close();
  return `${result.filename} 저장을 완료했습니다.`;
}

export async function chooseSaveDirectory(): Promise<string> {
  const directoryHandle = await pickDirectory();
  if (!directoryHandle) {
    return "저장 폴더를 선택하지 않았습니다.";
  }
  return `${directoryHandle.name} 폴더를 저장 위치로 선택했습니다.`;
}

export async function openSaveDirectory(): Promise<string> {
  let directoryHandle = await getStoredDirectoryHandle();
  if (!directoryHandle || !(await ensureWritePermission(directoryHandle))) {
    directoryHandle = await pickDirectory();
  }

  if (!directoryHandle) {
    return "저장 폴더를 선택하지 않았습니다.";
  }

  let openedHandle: DirectoryHandle | null = null;
  try {
    openedHandle = await pickDirectory(directoryHandle);
  } catch {
    openedHandle = await pickDirectory();
  }
  if (!openedHandle) {
    return `${directoryHandle.name} 폴더가 저장 위치로 설정되어 있습니다.`;
  }

  return `${openedHandle.name} 폴더를 저장 위치로 선택했습니다.`;
}

export async function saveProcessedPdf(result: ProcessedPdf): Promise<string> {
  const directoryHandle = await getStoredDirectoryHandle();
  if (directoryHandle && (await ensureWritePermission(directoryHandle))) {
    await writePdfToDirectory(directoryHandle, result);
    return `${directoryHandle.name} 폴더에 ${result.filename} 저장을 완료했습니다.`;
  }

  const pickerMessage = await savePdfWithFilePicker(result);
  if (pickerMessage) return pickerMessage;

  const supportsDirectoryPicker = typeof (window as WindowWithDirectoryPicker).showDirectoryPicker === "function";
  if (!supportsDirectoryPicker) {
    triggerDownload(result);
    return "브라우저가 폴더 직접 저장을 지원하지 않아 다운로드로 저장했습니다.";
  }

  const nextDirectoryHandle = await pickDirectory();
  if (!nextDirectoryHandle) {
    triggerDownload(result);
    return "저장 폴더를 선택하지 않아 다운로드로 저장했습니다.";
  }

  await writePdfToDirectory(nextDirectoryHandle, result);
  return `${nextDirectoryHandle.name} 폴더에 ${result.filename} 저장을 완료했습니다.`;
}
