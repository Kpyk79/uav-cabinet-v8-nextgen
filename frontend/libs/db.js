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
    },

    showNotification(msg, type = 'info') {
        const id = 'notification-' + Date.now();
        const div = document.createElement('div');
        div.id = id;
        div.innerHTML = `
            <div class="fixed top-4 right-4 z-[9999] glass p-4 rounded-2xl shadow-2xl border-l-4 transition-all duration-300 translate-x-full opacity-0 flex items-center gap-3">
                <div class="w-2 h-2 rounded-full animate-pulse"></div>
                <div class="text-[11px] font-black uppercase tracking-wider text-white">${msg}</div>
            </div>
        `;

        const inner = div.firstElementChild;
        if (type === 'error') inner.classList.add('border-red-500', 'bg-red-500/10');
        else if (type === 'success') inner.classList.add('border-green-500', 'bg-green-500/10');
        else inner.classList.add('border-blue-500', 'bg-blue-500/10');

        const dot = inner.querySelector('.animate-pulse');
        if (type === 'error') dot.classList.add('bg-red-500');
        else if (type === 'success') dot.classList.add('bg-green-500');
        else dot.classList.add('bg-blue-500');

        document.body.appendChild(inner);

        // Trigger animation
        requestAnimationFrame(() => {
            inner.classList.remove('translate-x-full', 'opacity-0');
        });

        // Remove after 5 seconds
        setTimeout(() => {
            inner.classList.add('translate-x-full', 'opacity-0');
            setTimeout(() => inner.remove(), 300);
        }, 5000);
    }
};

window.dbAPI = dbAPI;
