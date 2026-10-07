# Quixotic Brain — Product Spec Index

`PRODUCT.md` (~7,497 tokens) is split into 67 section files in `docs/product/` (largest ~449 tokens). Read this index, then open only the file(s) you need. Token counts are estimates (~4 chars/token).

## Quick lookup

| If you need… | Open |
|---|---|
| What the product is, goals, non-goals | 01, 04, 05 |
| Roles & permissions (RBAC) | 09, 42 |
| Ask Brain behaviour, modes, example | 11 |
| Knowledge entry, approval states, versions | 12, 15 |
| Uploading documents | 13 |
| Sales memory & Discord import | 16–19 |
| Retrieval pipeline | 07, 24–27 |
| Answer rules (sources, confidence, no hallucination, priority) | 20, 29–32 |
| API endpoints & keys | 37–40 |
| Stack, AWS, database | 43–50 |
| Security & audit | 51–53 |
| Phases & acceptance criteria | 61, 63, 64 |

## Vision & scope

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 1 | Product Overview | [01-product-overview.md](01-product-overview.md) | 209 | Name, type, org, AWS target, primary users; "One Brain. Multiple Quixotic products." |
| 2 | Product Vision | [02-product-vision.md](02-product-vision.md) | 126 | Quixotic Brain should become the primary internal knowledge infrastructure of Quixotic AI. |
| 3 | Core Problems | [03-core-problems.md](03-core-problems.md) | 208 | Quixotic currently has knowledge distributed across: Employees, Internal documents, Department-specific files, Sales scripts |
| 4 | Product Goals | [04-product-goals.md](04-product-goals.md) | 236 | Quixotic Brain should: Centralize company knowledge., Provide natural-language search., Support English, Urdu, Roman Urdu, and mix |
| 5 | Non-Goals for V1 | [05-non-goals-for-v1.md](05-non-goals-for-v1.md) | 117 | The following should **not** be included in V1: Kubernetes, Complex multi-agent systems, GraphRAG, Knowledge graphs |
| 6 | Core Architecture | [06-core-architecture.md](06-core-architecture.md) | 175 | Diagram: Knowledge + Sales Memory + Business Rules -> RAG engine -> API layer -> apps |
| 7 | RAG Retrieval Architecture | [07-rag-retrieval-architecture.md](07-rag-retrieval-architecture.md) | 159 | Pipeline: auth, permissions, filters, normalize, BM25 + BGE-M3, rerank 20-40 to 5-8, LLM, sources |
| 8 | Product Modules | [08-product-modules.md](08-product-modules.md) | 43 | Quixotic Brain contains six primary modules: Ask Brain, Knowledge Base, Sales Memory, Knowledge Ingestion |

## People & structure

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 9 | User Roles | [09-user-roles.md](09-user-roles.md) | 280 | Employee, Contributor, Manager, Administrator: what each can and cannot do |
| 10 | Department Structure | [10-department-structure.md](10-department-structure.md) | 94 | Initial departments: Create departments, Rename departments, Archive departments, Assign users |

## Ask Brain & knowledge

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 11 | Ask Brain | [11-ask-brain.md](11-ask-brain.md) | 449 | Ask Brain is the main employee-facing interface. |
| 12 | Knowledge Base | [12-knowledge-base.md](12-knowledge-base.md) | 255 | Knowledge types, Add Knowledge form (no technical terms), approval workflow, tracked fields |
| 13 | Document Upload | [13-document-upload.md](13-document-upload.md) | 155 | V1 file types, upload form, processing pipeline (extract, chunk, embed, index) |
| 14 | Metadata Model | [14-metadata-model.md](14-metadata-model.md) | 133 | Metadata JSON per chunk; used for access, filtering, versions, analytics |
| 15 | Version Control | [15-version-control.md](15-version-control.md) | 92 | Current information must always override old information. |

## Sales memory & intelligence

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 16 | Sales Memory | [16-sales-memory.md](16-sales-memory.md) | 187 | Quixotic currently has approximately 7,000 historical Discord sales conversations. |
| 17 | Discord Import | [17-discord-import.md](17-discord-import.md) | 167 | Discord JSON import UI and 15-step processing pipeline |
| 18 | Privacy and Data Cleaning | [18-privacy-and-data-cleaning.md](18-privacy-and-data-cleaning.md) | 101 | Before historical chats are indexed, remove unnecessary personal information. |
| 19 | Sales Intelligence | [19-sales-intelligence.md](19-sales-intelligence.md) | 137 | The Brain should eventually answer: Explain value, Ask customer budget, Reduce scope, Offer alternative package |
| 20 | Knowledge Priority Rules | [20-knowledge-priority-rules.md](20-knowledge-priority-rules.md) | 109 | The Brain must follow this hierarchy: Current Company Policy, Approved SOP / Script, Approved Management Instruction, Historical S |
| 21 | Feedback Loop | [21-feedback-loop.md](21-feedback-loop.md) | 88 | After an answer: User question, Retrieved knowledge, AI answer, Agent action |

## Language & retrieval

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 22 | Language Support | [22-language-support.md](22-language-support.md) | 74 | Required: English, Urdu, Roman Urdu, Mixed English + Urdu |
| 23 | Roman Urdu Normalization | [23-roman-urdu-normalization.md](23-roman-urdu-normalization.md) | 70 | Roman Urdu normalization example; keep the original query for audit |
| 24 | Embedding Layer | [24-embedding-layer.md](24-embedding-layer.md) | 173 | Initial recommended model to evaluate: Multilingual, Suitable for English, Suitable for multilingual retrieval, Good fit for Urdu- |
| 25 | Keyword Search | [25-keyword-search.md](25-keyword-search.md) | 43 | BM25: exact names, codes, IDs, acronyms, error codes |
| 26 | Hybrid Search | [26-hybrid-search.md](26-hybrid-search.md) | 61 | Hybrid Search combines: Improve exact-match retrieval, Improve semantic retrieval, Improve mixed-language search, Reduce failures  |
| 27 | Reranking | [27-reranking.md](27-reranking.md) | 79 | Hybrid search should return approximately: Direct relevance, Current information, Official knowledge, Scenario similarity |
| 28 | LLM Generation Layer | [28-llm-generation-layer.md](28-llm-generation-layer.md) | 69 | Replaceable LLM layer (OpenAI, Gemini, Claude, Bedrock, local); generate_answer() |

## Answer quality

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 29 | Hallucination Protection | [29-hallucination-protection.md](29-hallucination-protection.md) | 100 | Answer only from retrieved knowledge; never invent policies or prices; "not found" reply |
| 30 | Sources | [30-sources.md](30-sources.md) | 69 | Source format (title, section, version, updated) and historical evidence counts |
| 31 | Confidence | [31-confidence.md](31-confidence.md) | 48 | Backend may calculate numeric scores internally. |
| 32 | Low Confidence Behavior | [32-low-confidence-behavior.md](32-low-confidence-behavior.md) | 54 | If confidence is low: Ask Manager, Report Missing Knowledge, Search Documents |

## Frontend & dashboards

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 33 | Frontend Navigation | [33-frontend-navigation.md](33-frontend-navigation.md) | 56 | Sidebar: Ask Brain, Knowledge, Sales Memory, Add Information, Documents, Insights + Admin items |
| 34 | Dashboard | [34-dashboard.md](34-dashboard.md) | 79 | Example: Recent Questions, Failed Questions, Most Asked Topics, Recently Updated Knowledge |
| 35 | Failed Questions | [35-failed-questions.md](35-failed-questions.md) | 63 | Failed questions list (low confidence, not found) with Add Missing Knowledge action |
| 36 | Knowledge Health | [36-knowledge-health.md](36-knowledge-health.md) | 60 | Knowledge health counters: active, outdated, no owner, stale, duplicates, conflicts |

## API & access

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 37 | API Platform | [37-api-platform.md](37-api-platform.md) | 54 | Core /v1 endpoints: ask, search, documents, sales-memory, feedback, health |
| 38 | Ask API | [38-ask-api.md](38-ask-api.md) | 120 | POST /v1/ask request and response JSON |
| 39 | Search API | [39-search-api.md](39-search-api.md) | 97 | Search-only endpoint returns raw retrieval results without LLM generation. |
| 40 | API Keys | [40-api-keys.md](40-api-keys.md) | 86 | Each internal Quixotic product should have its own credentials. |
| 41 | Authentication | [41-authentication.md](41-authentication.md) | 31 | V1: Email or employee ID, Password, Google Workspace SSO, Microsoft SSO |
| 42 | Authorization | [42-authorization.md](42-authorization.md) | 42 | RBAC flow: user, role, department, permissions, metadata filter, retrieval (before retrieval) |

## Infrastructure & data

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 43 | Infrastructure | [43-infrastructure.md](43-infrastructure.md) | 55 | Why AWS (credits, private networking, RDS, S3, ECS, SQS, CloudWatch) |
| 44 | V1 Infrastructure | [44-v1-infrastructure.md](44-v1-infrastructure.md) | 102 | V1 stack per layer: Next.js/Vercel, FastAPI/ECS, RDS pgvector, S3, SQS, BGE-M3, Bedrock |
| 45 | Database Strategy | [45-database-strategy.md](45-database-strategy.md) | 92 | Initial recommendation: Users, Departments, Roles, Permissions |
| 46 | Raw File Storage | [46-raw-file-storage.md](46-raw-file-storage.md) | 35 | S3 buckets/paths: raw/documents, raw/discord, processed, exports, backups |
| 47 | Background Jobs | [47-background-jobs.md](47-background-jobs.md) | 90 | Async jobs via SQS + ECS workers; frontend shows progress |
| 48 | Frontend Stack | [48-frontend-stack.md](48-frontend-stack.md) | 46 | Recommended: Clean, Minimal, Non-technical, Fast |
| 49 | Backend Stack | [49-backend-stack.md](49-backend-stack.md) | 56 | Recommended: Strong AI ecosystem, Easy embedding model integration, Good API design, Async support |
| 50 | Suggested Repository Structure | [50-suggested-repository-structure.md](50-suggested-repository-structure.md) | 86 | Repo layout: frontend, backend modules, workers, evaluation, migrations, docs |

## Security & operations

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 51 | Security Requirements | [51-security-requirements.md](51-security-requirements.md) | 84 | Must include: HTTPS, Private RDS, Private S3 buckets, Encrypted database |
| 52 | Prompt Injection Protection | [52-prompt-injection-protection.md](52-prompt-injection-protection.md) | 56 | Documents are data, never instructions; malicious-document example |
| 53 | Audit Logs | [53-audit-logs.md](53-audit-logs.md) | 60 | Track: User login, Document upload, Knowledge submission, Approval |
| 54 | Backup Strategy | [54-backup-strategy.md](54-backup-strategy.md) | 43 | Backups: RDS automatic, S3 versioning, metadata, config |
| 55 | Monitoring | [55-monitoring.md](55-monitoring.md) | 57 | CloudWatch metrics: errors, latency, CPU, queue depth, model latencies |
| 56 | Performance Targets | [56-performance-targets.md](56-performance-targets.md) | 51 | Targets: search < 2s, full answer 5-8s, dashboard < 2s, instant upload acceptance |

## Scale, evaluation & cost

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 57 | Expected Initial Scale | [57-expected-initial-scale.md](57-expected-initial-scale.md) | 62 | Employees: Kubernetes, Distributed vector clusters, Massive GPU infrastructure |
| 58 | Evaluation | [58-evaluation.md](58-evaluation.md) | 80 | Company-specific evaluation question set with expected sources |
| 59 | Evaluation Metrics | [59-evaluation-metrics.md](59-evaluation-metrics.md) | 82 | Measure: Recall@5, Recall@10, MRR, Reranker quality |
| 60 | Cost Strategy | [60-cost-strategy.md](60-cost-strategy.md) | 76 | Main goal: Oversized GPUs running permanently, Large embedding models without evidence, Unnecessary infrastructure, Complex micros |

## Plan & success

| # | Section | File | ~Tok | Covers |
|---|---|---|---|---|
| 61 | Development Phases | [61-development-phases.md](61-development-phases.md) | 242 | Build: Authentication, Departments, User roles, Document upload |
| 62 | Key User Stories | [62-key-user-stories.md](62-key-user-stories.md) | 192 | User stories: employee, sales agent, manager, admin, developer |
| 63 | Acceptance Criteria | [63-acceptance-criteria.md](63-acceptance-criteria.md) | 166 | Quixotic Brain V1 is considered complete when: Employees can log in, Roles and departments work, Admin can upload files, Admin can |
| 64 | V1 Success Criteria | [64-v1-success-criteria.md](64-v1-success-criteria.md) | 143 | The product is successful if: Employees can retrieve company knowledge reliably., Admins can update knowledge without coding., Dep |
| 65 | Core Product Principle | [65-core-product-principle.md](65-core-product-principle.md) | 121 | Core principle: knowledge belongs to the Brain; apps consume it, never duplicate it |
| 66 | Future Product Possibility | [66-future-product-possibility.md](66-future-product-possibility.md) | 116 | If Quixotic Brain proves successful internally, it could later evolve into a multi-company SaaS product. |
| 67 | Final Product Definition | [67-final-product-definition.md](67-final-product-definition.md) | 122 | Final definition: not just a chatbot; engine, RAG platform, sales memory, API, assistant |

## Conventions

- Every file is self-contained and starts with a comment naming its section number.
- Cross-references use section numbers; jump to `NN-*.md`.
- Source of truth is `PRODUCT.md`; edit it, then re-run `python docs/product/split.py`.
