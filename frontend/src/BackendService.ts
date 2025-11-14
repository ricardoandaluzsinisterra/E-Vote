class BackendService {
    private baseURL: string;

    constructor(baseURL: string) {
        // Use environment variable or default to localhost
        this.baseURL = import.meta.env.VITE_API_URL || baseURL;
    }

    // Your methods here...
}

export default new BackendService('http://localhost:8000');

