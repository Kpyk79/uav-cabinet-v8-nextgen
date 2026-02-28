const DB_NAME = 'UAV_Cabinet_DB';
const DB_VERSION = 1;

const initDB = () => {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = event => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('meta')) db.createObjectStore('meta', { keyPath: 'id' });
            if (!db.objectStoreNames.contains('drones')) db.createObjectStore('drones', { keyPath: 'unit' });
            if (!db.objectStoreNames.contains('drafts')) db.createObjectStore('drafts', { keyPath: 'id', autoIncrement: true });
            if (!db.objectStoreNames.contains('reports')) db.createObjectStore('reports', { keyPath: 'id' });
            if (!db.objectStoreNames.contains('syncQueue')) db.createObjectStore('syncQueue', { keyPath: 'id', autoIncrement: true });
        };

        request.onsuccess = event => resolve(event.target.result);
        request.onerror = event => reject(event.target.error);
    });
};

const dbAPI = {
    async saveMeta(data) {
        const db = await initDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('meta', 'readwrite');
            tx.objectStore('meta').put({ id: 'options', ...data });
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
    },

    async getMeta() {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('meta', 'readonly');
            const req = tx.objectStore('meta').get('options');
            req.onsuccess = () => resolve(req.result);
            req.onerror = () => resolve(null);
        });
    },

    async saveDrones(unit, drones) {
        const db = await initDB();
        return new Promise((resolve, reject) => {
            const tx = db.transaction('drones', 'readwrite');
            tx.objectStore('drones').put({ unit, drones });
            tx.oncomplete = () => resolve();
        });
    },

    async getDrones(unit) {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('drones', 'readonly');
            const req = tx.objectStore('drones').get(unit);
            req.onsuccess = () => resolve(req.result ? req.result.drones : []);
            req.onerror = () => resolve([]);
        });
    },

    async saveDrafts(drafts) {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('drafts', 'readwrite');
            const store = tx.objectStore('drafts');
            store.clear();
            drafts.forEach(d => store.add(d));
            tx.oncomplete = () => resolve();
        });
    },

    async getDrafts() {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('drafts', 'readonly');
            const req = tx.objectStore('drafts').getAll();
            req.onsuccess = () => resolve(req.result);
        });
    },

    async addToSyncQueue(type, payload) {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('syncQueue', 'readwrite');
            tx.objectStore('syncQueue').add({ type, payload, timestamp: Date.now() });
            tx.oncomplete = () => resolve();
        });
    },

    async getSyncQueue() {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('syncQueue', 'readonly');
            const req = tx.objectStore('syncQueue').getAll();
            req.onsuccess = () => resolve(req.result);
        });
    },

    async removeFromSyncQueue(id) {
        const db = await initDB();
        return new Promise((resolve) => {
            const tx = db.transaction('syncQueue', 'readwrite');
            tx.objectStore('syncQueue').delete(id);
            tx.oncomplete = () => resolve();
        });
    }
};

window.dbAPI = dbAPI;
