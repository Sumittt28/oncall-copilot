import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Store for mock localStorage
let store: Record<string, string> = {};

// Mock localStorage before any imports
const localStorageMock = {
  getItem: vi.fn((key: string) => store[key] || null),
  setItem: vi.fn((key: string, value: string) => {
    store[key] = value;
  }),
  removeItem: vi.fn((key: string) => {
    delete store[key];
  }),
  clear: vi.fn(() => {
    store = {};
  }),
};

// Set up localStorage mock globally
vi.stubGlobal("localStorage", localStorageMock);

// Now import the api module
const { api } = await import("../lib/api");

describe("ApiClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    store = {};
  });

  afterEach(() => {
    api.logout();
  });

  describe("token management", () => {
    it("starts without a token when localStorage is empty", () => {
      // The api client initializes without a token when storage is empty
      api.logout(); // Ensure clean state
      expect(api.getToken()).toBeNull();
    });

    it("sets token and stores in localStorage", () => {
      api.setToken("test-token");
      expect(api.getToken()).toBe("test-token");
      expect(localStorageMock.setItem).toHaveBeenCalledWith("token", "test-token");
    });

    it("removes token on logout", () => {
      api.setToken("test-token");
      api.logout();
      expect(api.getToken()).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("token");
    });

    it("clears token when set to null", () => {
      api.setToken("test-token");
      api.setToken(null);
      expect(api.getToken()).toBeNull();
      expect(localStorageMock.removeItem).toHaveBeenCalledWith("token");
    });
  });

  describe("API requests", () => {
    beforeEach(() => {
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      vi.stubGlobal("localStorage", localStorageMock);
    });

    it("makes GET request to correct URL", async () => {
      const mockResponse = { items: [], total: 0 };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      api.setToken("test-token");
      const result = await api.getIncidents();

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/incidents",
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
            Authorization: "Bearer test-token",
          }),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it("includes query params for filtered requests", async () => {
      const mockResponse = { items: [], total: 0 };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      api.setToken("test-token");
      await api.getIncidents({ status: "open", limit: 10, offset: 5 });

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("status=open"),
        expect.anything()
      );
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("limit=10"),
        expect.anything()
      );
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("offset=5"),
        expect.anything()
      );
    });

    it("makes POST request with body", async () => {
      const mockResponse = { id: 1, title: "Test" };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      api.setToken("test-token");
      const result = await api.createIncident({
        title: "Test Incident",
        description: "Test description",
        severity: "SEV-3",
      });

      expect(global.fetch).toHaveBeenCalledWith(
        "http://localhost:8000/api/v1/incidents",
        expect.objectContaining({
          method: "POST",
          body: JSON.stringify({
            title: "Test Incident",
            description: "Test description",
            severity: "SEV-3",
          }),
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it("throws error on failed request", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: false,
        json: () => Promise.resolve({ detail: "Not found" }),
      });

      api.setToken("test-token");
      await expect(api.getIncident(999)).rejects.toThrow("Not found");
    });

    it("handles network errors gracefully", async () => {
      (global.fetch as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error("Network error")
      );

      api.setToken("test-token");
      await expect(api.getIncidents()).rejects.toThrow("Network error");
    });

    it("requests without token when not authenticated", async () => {
      const mockResponse = { items: [], total: 0 };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      // Ensure no token
      api.logout();

      await api.getIncidents();

      const callArgs = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      const headers = callArgs[1].headers as Record<string, string>;
      expect(headers["Authorization"]).toBeUndefined();
    });
  });

  describe("search endpoint", () => {
    beforeEach(() => {
      vi.stubGlobal("fetch", vi.fn());
    });

    afterEach(() => {
      vi.unstubAllGlobals();
      vi.stubGlobal("localStorage", localStorageMock);
    });

    it("encodes query parameters correctly", async () => {
      const mockResponse = { results: [], query: "test query", total: 0 };
      (global.fetch as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      api.setToken("test-token");
      await api.search("test query", 5);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("q=test%20query"),
        expect.anything()
      );
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("limit=5"),
        expect.anything()
      );
    });
  });
});
