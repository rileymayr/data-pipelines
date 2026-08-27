const DB_NAME = "teamwork-dynamics-session";
const STORE = "session";
const KEY = "current";
const VERSION = 1;

function openDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, VERSION);
        request.onupgradeneeded = () => request.result.createObjectStore(STORE);
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function put(value) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(STORE, "readwrite").objectStore(STORE).put(value, KEY);
        request.onsuccess = resolve;
        request.onerror = () => reject(request.error);
    });
}

async function get() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(STORE).objectStore(STORE).get(KEY);
        request.onsuccess = () => resolve(request.result || null);
        request.onerror = () => reject(request.error);
    });
}

async function clear() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
        const request = db.transaction(STORE, "readwrite").objectStore(STORE).delete(KEY);
        request.onsuccess = resolve;
        request.onerror = () => reject(request.error);
    });
}

async function compress(text) {
    if (!window.CompressionStream) return {encoding: "text", value: text};
    const stream = new Blob([text]).stream().pipeThrough(new CompressionStream("gzip"));
    return {encoding: "gzip", value: await new Response(stream).arrayBuffer()};
}

async function decompress(value) {
    if (value.encoding === "text") return value.value;
    const stream = new Blob([value.value]).stream().pipeThrough(new DecompressionStream("gzip"));
    return await new Response(stream).text();
}

export async function saveSession(session) {
    const existing = await get();
    const record = {...existing, ...session, version: VERSION, savedAt: Date.now()};
    if (typeof session.dataframe === "string") record.dataframe = await compress(session.dataframe);
    await put(record);
}

export async function loadSession() {
    const session = await get();
    if (!session || session.version !== VERSION) return null;
    if (session.dataframe) session.dataframe = await decompress(session.dataframe);
    return session;
}

export async function clearSession() { await clear(); }

window.session_cache = {save_session: saveSession, load_session: loadSession, clear_session: clear,
    save_dataframe: async (csv) => saveSession({dataframe: csv}),
    load_dataframe: async () => { const s = await loadSession(); return s && s.dataframe; }};
