from app.services.trace_store.memory_store import InMemoryTraceStore


# Single shared trace store for the entire application.
store = InMemoryTraceStore()