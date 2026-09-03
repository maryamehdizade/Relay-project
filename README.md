Maryam Mehdizade

## Architecture

```text
React Frontend
      │
      ▼
Django + DRF
      │
      ▼
   RabbitMQ
      │
      ▼
  AI Worker
      │
      ▼
  LangGraph
   ├── PostgreSQL
   ├── ChromaDB
   ├── Web Search
   └── Action Tools

AI Worker
      │
      ▼
   RabbitMQ
      │
      ▼
 Django SSE
      │
      ▼
    React