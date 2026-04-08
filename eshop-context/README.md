# eShop Context

> Curated excerpts from the [Microsoft eShop](https://github.com/dotnet-architecture/eShop) reference application (MIT License). Used by the triage node as **grounding context** for the LLM call.

## Why curated, not the full repo

The full eShop repo is large. For a 48-hour hackathon and a 30-second triage SLO, dumping the whole codebase into the prompt is wasteful and slow. Instead, `@developer` (HU-004) will pre-extract a small set of high-signal files into this folder:

- `architecture-overview.md` — what the services are and how they talk
- `services-map.md` — list of microservices, their ports, and their owners
- `known-failure-points.md` — common failure modes (DB connection, auth, payment processor)
- `code-excerpts/` — short representative excerpts of the most-touched files

The triage node calls `app.agent.tools.eshop_context.fetch_relevant_excerpts(report_text)` which does a simple keyword/embedding match against this folder and returns the top-3.

## Production path

In production, this folder is replaced by a vector store (pgvector, Qdrant, or LanceDB) that indexes the full eShop repo plus the team's runbooks. See `SCALING.md` §6.

## License

Excerpts retain the original eShop MIT license. The `LICENSE` at the repo root applies to original code in this project.
