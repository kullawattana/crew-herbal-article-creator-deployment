# Herbal Article Creator

Herbal Article Creator is a modular multi-agent system that discovers, verifies, and composes Thai-language articles and fact sheets about medicinal herbs for modern wellness and consumer-facing applications. The system combines automated literature retrieval (e.g., PubMed/NCBI), trend discovery, regulatory and safety checks, and cultural/local-knowledge review to produce evidence-backed, culturally sensitive, and audit-ready content. Outputs include human-readable articles, structured fact sheets, KPI evaluations, and machine-readable JSON for downstream consumption.

## Core idea
- Combine high-quality scientific evidence (e.g., PubMed/NCBI) with real-world trend signals and curated local traditional knowledge to produce trustworthy, contextualized herbal content.
- Use a modular multi-agent pipeline where specialized agents (trend discovery, literature research, safety/compliance, cultural review, lab-evidence synthesis, planning, writing, formatting, and QA) each perform a focused task; the `Crew` orchestrator sequences and aggregates agent outputs.
- Apply RAG/local-context lookups and evidence-deduplication so claims are accompanied by concise, verifiable citations and local knowledge references.
- Prioritize reproducibility and auditability: every article is produced with task artifacts, claim-level evidence, KPI evaluations, and an audit report (all saved in `outputs/`) so editorial teams can review and retrace decisions.
- Keep LLMs and external connectors pluggable and configurable via environment variables so the system can adapt providers, embedding stores, and API limits without code changes.

## Key features

- Agent ecosystem: a modular multi-agent design with primary content agents (Trend Analyst, Research Agent, Compliance Checker, Cultural Editor, Writer Agent) plus specialist/support agents (Herbal Laboratory, Safety Inspector, Clinical Toxicologist, Internal Knowledge, Planner, QA/Auditor, Content Strategist, Formatter) and a KPI Evaluator.

- Evidence pipeline: automated literature and web retrieval (PubMed/NCBI, trend sources), deduplication, RAG/local-context lookup, concise evidence summaries and claim-level citations suitable for general readers and editorial review.

- Multi-layer safety & compliance: layered checks including regulatory mapping (Thai FDA and similar), safety inspector rules (contraindications, interactions, allergens), and clinical toxicology interpretation for risk-sensitive recommendations.

- Content planning & formats: Planner and Content Strategist produce section-level briefs, audience/format recommendations, and content variants; Formatter and output writers produce TXT, DOCX, and upload-ready artifacts.

- KPI & audit: Machine-readable KPI scoring (scientific accuracy, cultural correctness, safety/compliance, clarity, usefulness) exported as JSON and used to drive QA/Audit workflows.

- Extensible LLM + data configuration: pluggable LLM provider support and data-source connectors controlled via environment variables (LLM_* keys, search API keys, Pinecone or other vector DB settings).

- Outputs & integrations: final articles, master fact sheets, audit reports and raw task artifacts are saved to `outputs/` and optionally uploaded to Google Drive or external stores via provided upload tools.

## Agents and responsibilities (what each agent does)
Below are the logical agent roles used by this project and where to look for their implementations or integration in the codebase.

- Trend Analyst Agent
	- Responsibility: Identify trending herbs, topics, and user-facing content angles by scraping/monitoring web sources, trend APIs, and internal usage signals. Produce candidate herbs and suggested angles (audience, tone, format) for downstream agents.
	- Code: Orchestrated by the crew; trend-related helpers and connectors live in `src/herbal_article_creator/tools` (see `browse_website_tools.py`, `tavily_tools.py`, and other trend helper modules).

- Herbal Laboratory Agent
	- Responsibility: Plan, request, and interpret structured laboratory-style checks (in-silico, dataset-driven or experimental metadata) useful to validate herbal constituents, extraction methods, or assay signals. Not a wet-lab runner — this agent focuses on collating lab-relevant evidence and metadata.
	- Code: helpers and experimental parsers can be added under `src/herbal_article_creator/tools` and `src/herbal_article_creator/tools/services` (e.g., integrate with `tools/services/*_search_service.py`).

- Research Agent
	- Responsibility: Query scientific literature sources (PubMed/NCBI and other indexed services), retrieve and deduplicate results, extract structured study metadata (title, authors, year, PMID/DOI), fetch abstracts/PDFs when available, and summarize evidence for each claim.
	- Code: Core search and parsing utilities live in `src/herbal_article_creator/tools/pubmed_tools.py`. Service wrappers and external adapters are available under `src/herbal_article_creator/tools/services/` (for example, `sac_search_service.py`, `fda_search_service.py`).

- Compliance Checker Agent
	- Responsibility: Map claims and recommendations to regulatory categories, perform safety and labeling checks, flag potential non-compliant or restricted claims, and surface required warnings or citations (Thai FDA and similar jurisdictions).
	- Code: Policy and rule-checking helpers are in `src/herbal_article_creator/tools/fda_tools.py` and `src/herbal_article_creator/tools/sac_tools.py` (and may call services under `src/herbal_article_creator/tools/services/`).

- Safety Inspector Agent
	- Responsibility: Perform focused safety checks beyond basic compliance: identify contraindications, drug interactions, allergen signals, and population-specific safety flags.
	- Code: builds on `src/herbal_article_creator/tools/fda_tools.py`, `src/herbal_article_creator/tools/sac_tools.py`, and service wrappers in `src/herbal_article_creator/tools/services`.

- Clinical Toxicologist Agent
	- Responsibility: Interpret toxicology evidence, convert exposure/toxicity metrics into human-readable risk summaries, and highlight when clinical consultation or lab testing is required.
	- Code: implement as a specialist module (e.g., `src/herbal_article_creator/tools/clinical_toxicology.py`) that the Research or Compliance agents can call when toxicology signals are present.

- Cultural Editor Agent
	- Responsibility: Ensure cultural accuracy and sensitivity, validate traditional uses and local terminology, resolve translation/terminology inconsistencies, and adapt voice/tone for Thai audiences while preserving scientific correctness.
	- Code: Cultural resources and curated facts are stored in `data/json/` (e.g., herbs knowledge JSON files). Helpers and validators live in `src/herbal_article_creator/tools/` and may use the RAG utilities for local-context lookups.

- Internal Knowledge Agent
	- Responsibility: Maintain and query the project's internal knowledge base (local JSONs, curated facts, translations, and editorial notes) to ensure consistent terminology and reuse of verified facts.
	- Code: uses `data/json/` for static knowledge and helper functions under `src/herbal_article_creator/tools` for indexing/search; optionally integrate with the RAG pipeline (Pinecone helpers in `pinecone_tools.py`).

- Planner Agent
	- Responsibility: Turn research outputs into a stepwise content plan or brief: define sections, required evidence for each section, and deadlines or action items for other agents.
	- Code: planner logic can live in `src/herbal_article_creator/tools/rag_manager_tools.py` or a new `planner.py` and invoked by `crew.py` before the Writer Agent runs.

- Writer Agent
	- Responsibility: Synthesize research summaries, trend insights, compliance flags, and cultural guidance into draft articles and content variants (short summaries, fact sheets, long-form pieces) in Thai. Provide structured outputs (sections, citations, suggested images/CTAs) for the Formatter Agent.
	- Code: The orchestration for article generation lives in `src/herbal_article_creator/crew.py` and `src/herbal_article_creator/main.py`. Formatting helpers and output writers are in `src/herbal_article_creator/tools/docx_tools.py` and `src/herbal_article_creator/tools/gdrive_upload_file_tools.py`.

- QA / Auditor Agent
	- Responsibility: Independently re-check the final article and metadata for data integrity, citation completeness, formatting issues, and KPI thresholds; produce an audit report with pass/fail and remediation suggestions.
	- Code: QA checks can reuse `src/herbal_article_creator/tools/common_rag.py`, `docx_tools.py`, and be exposed as `tools/qa_auditor.py` so `crew.py` can run it as a final step.

- Content Strategist Agent
	- Responsibility: Recommend publishing angles, target audience segments, SEO/keyphrase suggestions, and distribution formats (short social post, long-read, fact sheet) based on Trend Analyst signals and KPI priorities.
	- Code: a lightweight helper in `src/herbal_article_creator/tools/content_strategist.py` that consumes trend outputs and returns recommended content strategies.

- Formatter Agent
	- Responsibility: Convert the Writer Agent's raw content into desired output formats — plain text, DOCX, and optionally upload-ready artifacts. Apply consistent headings, captions, references, and styling.
	- Code: extend `src/herbal_article_creator/tools/docx_tools.py` and add formatters under `src/herbal_article_creator/tools/formatters.py` for HTML/DOCX/TXT pipelines.

Note: The repository orchestrates agents rather than having rigid one-file-per-agent class names. The main orchestration is in `src/herbal_article_creator/crew.py`, and supporting modules are grouped under `src/herbal_article_creator/tools` and `src/herbal_article_creator/tools/services`.


## Task and responsibilities (what each agent does)

This section describes concrete tasks each agent performs, the inputs they expect, the outputs they produce, and short examples of checks or decisions they make. Use these as a blueprint when adding new agent implementations or wiring the orchestration in `crew.py`.

- Trend Analyst
	- Inputs: seed herbs or topic keywords, trend API results, web scraping results, internal usage metrics.
	- Tasks: discover candidate herbs and topical angles, score trends by recency and relevance, recommend audience/tone/format (e.g., short social post vs. long fact sheet).
	- Outputs: ranked candidate list with metadata (source, signal strength, suggested angles).
	- Example checks: filter out low-signal sources; suppress obviously promotional content.

- Herbal Laboratory Agent
	- Inputs: herb identifier, extraction/processing queries, links to experimental papers or datasets.
	- Tasks: collect in-silico / experimental metadata (assay types, extraction methods, compound names), normalize units, and flag likely lab evidence quality (in-vitro vs. in-vivo vs. human trial).
	- Outputs: structured lab-evidence records and interpretation notes (confidence, limitations).
	- Example checks: detect when only in-vitro evidence exists and add a caution note for clinical claims.

- Research Agent
	- Inputs: herb/topic, search limits and filters, optional NCBI API key and polite delay settings.
	- Tasks: query literature sources, deduplicate results, extract study metadata (title, authors, year, PMID/DOI), fetch abstracts/PDFs where available, and create concise evidence summaries.
	- Outputs: claim-linked evidence bundles (source, excerpt, structured metadata) and short summaries for each claim.
	- Example checks: prioritize systematic reviews and randomized trials over single-case reports when present.

- Compliance Checker
	- Inputs: draft claims or proposed recommendations from other agents, regulatory rule set (local config, e.g., Thai FDA rules).
	- Tasks: map claims to regulatory categories (allowed, restricted, prescription-only), suggest required disclaimers, and mark claims needing legal review.
	- Outputs: compliance flags, required warning text, and a compliance score per article section.
	- Example checks: flag therapeutic claims (e.g., 'treats disease X') as restricted if they fall under medical claims.

- Safety Inspector
	- Inputs: ingredients list, known population constraints (pregnancy, pediatrics), drug lists for interaction checks.
	- Tasks: identify contraindications, probable drug–herb interactions, allergen risks, and population-specific safety concerns.
	- Outputs: structured safety report with severity levels and recommended user-facing warnings.
	- Example checks: cross-check herb constituents against a drug-interaction database and surface severe interactions.

- Clinical Toxicologist
	- Inputs: toxicology signals from literature or ADME data, reported case studies, dose/exposure details.
	- Tasks: translate toxicology metrics into human-readable risk summaries, recommend when clinical tests or referrals are needed, and suggest safe dosing ranges when data supports it.
	- Outputs: toxicology summary, recommended actions, and confidence level.
	- Example checks: convert an LD50 or NOAEL signal into contextual warnings when human-equivalent exposures are close to reported use.

- Internal Knowledge Agent
	- Inputs: local JSON knowledge files, editorial notes, translation maps, previously approved fact sheets.
	- Tasks: answer project-internal queries (canonical names, preferred translations, previously validated facts), de-duplicate facts, and provide citation to internal sources.
	- Outputs: canonical term mappings, editorial notes, and references to internal files.
	- Example checks: prefer the project's canonical herb name and terminology when multiple synonyms exist.

- Planner Agent
	- Inputs: chosen herb/angle, evidence bundles, KPI targets and audience guidance.
	- Tasks: create a content plan with sections, required evidence per section, deadlines/tasks for other agents, and a prioritized checklist for the Writer Agent.
	- Outputs: structured content brief (section list, required claims, minimum evidence thresholds, tone guidelines).
	- Example checks: ensure each section meets a minimum number of independent evidence items when KPI requires it.

- Writer Agent
	- Inputs: content plan, evidence bundles, compliance & safety flags, cultural notes.
	- Tasks: generate draft text in Thai across requested variants (short summary, long-form, fact sheet), include inline citations, and surface uncertain claims for review.
	- Outputs: article drafts with section markers, inline citation IDs, short summary variants, and a claim-verification checklist.
	- Example checks: mark any claim supported only by low-quality evidence and annotate it with an editor action item.

- Formatter Agent
	- Inputs: article drafts, citation bundles, formatting templates.
	- Tasks: convert drafts into target output formats (plain text, DOCX, HTML), apply consistent headings, insert reference lists, and prepare uploadable artifacts.
	- Outputs: formatted files (TXT/DOCX/HTML) and an export manifest (filenames, checksums, metadata).
	- Example checks: confirm that every inline citation resolves to a citation record present in the manifest.

- Content Strategist
	- Inputs: trend signals, KPI priorities, draft content variants.
	- Tasks: recommend audience targeting, distribution formats, SEO/keyphrase suggestions, and repackaging strategies (e.g., social snippets, infographics).
	- Outputs: strategy brief and prioritized distribution plan.
	- Example checks: ensure keyphrases are present in headings and summaries where appropriate.

- QA / Auditor Agent
	- Inputs: final formatted artifacts, KPI evaluations, claim verification checklist.
	- Tasks: run independent checks (citation completeness, formatting rules, KPI threshold validation), produce an audit report with pass/fail and remediation steps, and optionally trigger re-run of specific agents.
	- Outputs: audit report JSON, human-readable audit summary, and remediation tasks.
	- Example checks: fail if any required citation is missing or if safety severity is above an acceptable threshold.

- KPI Evaluator
	- Inputs: article drafts, evidence and audit signals, scoring rules (configurable in YAML/JSON).
	- Tasks: compute scores for scientific accuracy, cultural correctness, safety/compliance, clarity, and usefulness; aggregate into an overall quality score and suggest improvement areas.
	- Outputs: KPI JSON with per-dimension scores and recommended fixes.
	- Example checks: lower scientific-accuracy score if claims lack supporting primary evidence.

Notes on orchestration
- The `Crew` orchestrator (`src/herbal_article_creator/crew.py`) is responsible for sequencing agents, handling retries/timeout policies, propagating task context (IDs, evidence links), and aggregating outputs into `outputs/`.
- Design principle: keep agents small and focused. Prefer passing structured data (dicts/JSON) between agents and persist task artifacts for auditability.


## Suggested internal code classes / components (mapping to the repo)
(these are conceptual mappings to help contributors understand where to add or extend functionality):

- `Crew` (orchestrator)
	- Location: `src/herbal_article_creator/crew.py`
	- Purpose: Top-level coordinator that sequentially or concurrently runs agent tasks, aggregates results, and writes outputs.

- Agent-like modules / helpers
	- Location: `src/herbal_article_creator/tools/*.py` and `src/herbal_article_creator/tools/services/*`
	- Purpose: Implement discrete responsibilities (search, compliance checks, formatting, uploading). Contributors can add classes or functions per agent in these files.

- CLI / Runner
	- Location: `src/herbal_article_creator/main.py`
	- Purpose: Entry point that loads configuration, parses CLI args, and invokes the `Crew` orchestration.

If you add explicit Agent classes, prefer a small base class or protocol (e.g., `Agent.run(input) -> output`) and implement each agent as a thin wrapper around existing helper functions.

## Environment variables and configuration
Core environment variables (.env.example):

- Herbal Name: `HERBS_FOR_RESEARCH`
- Search API KEY: `TAVILY_API_KEY`
- Pubmed API Key: `NCBI_API_KEY`, `PUBMED_CONTACT_EMAIL`, `PUBMED_POLITE_DELAY`
- LLM: `LLM_MODEL`, `LLM_LLAMA_MODEL`, `LLM_GEMINI_MODEL`, `LLM_GPT_MODEL`, `LLM_CLAUDE_MODEL`
- LLM Gemini Embeddings RAG API Key: `GOOGLE_API_KEY`
- LLM API KEY: `NVIDIA_NIM_API_KEY`, `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- LLM Parameters: `LLM_TEMPERATURE`, `LLM_TOP_P`, `LLM_MAX_TOKENS`
- LLM control of request search: `RESEARCH_MAX_CALLS`, 
- Pinecone Vector Database API Key: `PINECONE_API_KEY`
- Pinecone Index Name (Database Name): `PINECONE_INDEX_NAME`, `PINECONE_NAMESPACE`
- Pinecone Gemini Embeddings Model: `PINECONE_EMBED_MODEL`, `PINECONE_DIMENSION`
- Pinecone Parameters: `PINECONE_TOP_K`, `PINECONE_SNIPPET_LIMIT`, `PINECONE_TOTAL_LIMIT`
- Pinecone Context building: `PINECONE_BUILD_INITIAL_CONTEXT`, `PINECONE_CONTEXT_TOP_K`, `PINECONE_CONTEXT_MAX_CHARS`
- Google Drive Upload file to folder ID after create final article: `GOOGLE_FOLDER_ID`
- Google Drive authentication Desktop for upload file: `GDRIVE_CLIENT_SECRET_PATH` 
- Google Drive Read file in folder for RAG: `GOOGLE_FOLDER_ID`
- Google Drive credentials service account with file path or base 64: `GOOGLE_SERVICE_ACCOUNT_JSON_PATH`, `GOOGLE_SERVICE_ACCOUNT_JSON_B64`
- Google Drive authentication Desktop for upload file: `GDRIVE_CLIENT_SECRET_PATH` 
- 

Recommended: copy a `.env.example` (if present) and fill values before running.

## Installation

Supported Python versions: 3.10–3.13

Notes before install
- Create or copy a `.env` file before running the system (see the `Environment variables and configuration` section). If the repository includes a `.env.example`, copy it and fill required keys (API keys, LLM settings, Google Drive credentials, Pinecone keys, etc.).

Using Poetry (recommended)

1. Clone and install dependencies:

```bash
git clone <repo-url>
cd crew-herbal-article-creator
poetry install
```

2. Create a runtime `.env` (example):

```bash
cp .env.example .env
# edit .env and set keys such as NCBI_API_KEY, TAVILY_API_KEY, NVIDIA_NIM_API_KEY, GOOGLE_SERVICE_ACCOUNT_JSON_PATH, etc.
```

3. Run the application:

```bash
poetry run python -m src.herbal_article_creator.main
```

4. Developer commands (with Poetry):

```bash
poetry run pytest        # run tests
poetry run black .       # format
poetry run isort .       # import sorting
poetry run mypy .        # type checking (if configured)
```

Using pip + virtualenv

1. Create and activate a virtual environment (macOS / Linux):

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
# optionally install the package in editable mode if pyproject.toml supports it
pip install -e .
```

3. Create `.env` and run:

```bash
cp .env.example .env
# edit .env and set required keys
python -m src.herbal_article_creator.main
```

Optional / troubleshooting
- If a `pyproject.toml` is present, prefer Poetry to preserve dependency resolution. `pip install -r requirements.txt` will work for many setups but may not replicate Poetry's lockfile resolution.
- If you plan to use cloud/vector stores (Pinecone) or Google Drive uploads, ensure the corresponding credentials are set in `.env` before running those features.
- For heavy LLM usage, set API keys and provider-specific variables (e.g., `NVIDIA_NIM_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`) and respect provider rate limits (use `RESEARCH_MAX_CALLS` to throttle search calls).
- On Windows, activate the venv with `.\.venv\Scripts\activate` (PowerShell/CMD) instead of `source`.

If you want, I can also add a `.env.example` file populated with the variables referenced in the README.

## Libraries and dependencies
This project has a number of runtime, optional, and developer dependencies. Exact versions are pinned in `requirements.txt` (for pip) and `pyproject.toml` (for Poetry). Use those files to reproduce a consistent environment; the list below summarizes the main packages and the purpose they serve.

Install all pinned dependencies with pip:

```bash
pip install -r requirements.txt
```

Or with Poetry (preferred if the project provides `pyproject.toml`):

```bash
poetry install
```

Core runtime (examples from `requirements.txt`)
- crewai[tools] — agentic orchestration helpers
- tavily-python — search / trend connector
- langchain / langchain-core / langchain-community — LLM orchestration
- google-generativeai — Google Gen AI SDK (if using Gemini)
- chromadb / pinecone — local/vector stores (choose one or both)
- requests or httpx — HTTP requests
- python-dotenv — load `.env` files
- pydantic / pydantic-settings — configuration and validation

PDF & document processing (optional)
- pdfplumber, PyPDF2, pymupdf, pypdfium2 — PDF parsing and extraction
- python-docx, markdown, beautifulsoup4, lxml — convert/format to DOCX or HTML

Google & Drive integrations (optional)
- google-api-python-client, google-auth, google-auth-httplib2, google-auth-oauthlib, pydrive2

Vector DB / memory / embeddings (optional)
- pinecone, chromadb, langchain-google-genai (embedding adapters)

OCR & scanned PDFs (optional)
- pytesseract, Pillow

LLM providers & helpers (choose provider-specific SDKs)
- NVIDIA NIM SDK (if used), google-generativeai, openai, anthropic, tavily-python

Evaluation & metrics (optional)
- rouge-score, sacrebleu

Developer & QA tools
- pytest — tests
- black, isort — formatting
- mypy — static type checks
- psutil — runtime/process utilities (used by performance helpers)

Notes & recommendations
- For full reproducibility prefer installing via Poetry if `pyproject.toml` / `poetry.lock` are present.
- Only enable/install the optional integrations you need (Google Drive, Pinecone, OCR, heavy LLM SDKs) to avoid unnecessary install size and API key exposure.
- If you need a minimal runtime, create a small requirements subset containing the packages you actually use in that deployment profile.

If you'd like, I can generate a trimmed `requirements-minimal.txt` and a `.env.example` based on the variables used in the README.

## Usage
Run with default settings:

```bash
crewai run
```

Outputs are stored in `outputs/` and may include:
- `benchmark_meta_model.json`
- `research_paper.docx`
- `task_<1>_<YYYYMMDD>_<HHMMSS>` - TRENDS_DATA
- `task_<2>_<YYYYMMDD>_<HHMMSS>` - LAB_DATA
- `task_<3>_<YYYYMMDD>_<HHMMSS>` - RESEARCH_DATA
- `task_<4>_<YYYYMMDD>_<HHMMSS>` - COMPLIANCE_DATA
- `task_<5>_<YYYYMMDD>_<HHMMSS>` - SAFETY_DATA
- `task_<6>_<YYYYMMDD>_<HHMMSS>` - TOXICITY_DATA
- `task_<7>_<YYYYMMDD>_<HHMMSS>` - RAW_THAI_DATA
- `task_<8>_<YYYYMMDD>_<HHMMSS>` - CULTURE_DATA (translate from Thai to English)
- `task_<9>_<YYYYMMDD>_<HHMMSS>` - HERBAL_INTERNAL_SUMMARY
- `task_<10>_<YYYYMMDD>_<HHMMSS>` - CULTURAL_INTERNAL_SUMMARY (RAG)
- `task_<11>_<YYYYMMDD>_<HHMMSS>` - MASTER_FACT_SHEET
- `task_<12>_<YYYYMMDD>_<HHMMSS>` - STRATEGIC_PLAN
- `task_<13>_<YYYYMMDD>_<HHMMSS>` - FINAL ARTICLE from MASTER_FACT_SHEET and STRATEGIC_PLAN
- `task_<14>_<YYYYMMDD>_<HHMMSS>` - AUDIT_DATA_INTEGRITY_REPORT (QA) from FINAL ARTICLE 
- `task_<15>_<YYYYMMDD>_<HHMMSS>` - AUDIT_STRATEGY_REPORT for final decission (Go/No Go)
- `task_<16>_<YYYYMMDD>_<HHMMSS>` - outputs/research_paper.docx
- `task_<16>_<YYYYMMDD>_<HHMMSS>` - uploaded file to google drive

## Project layout (high level)
- `src/herbal_article_creator/` – core code (crew, main, tools)
- `data/` – static data, JSONs, PDFs
- `outputs/` – generated articles and KPI JSONs
- `.env`, `pyproject.toml`, `requirements.txt`

## Troubleshooting / common issues
- Verify Python version and that dependencies are installed in the active environment
- If PubMed rate-limited: add `NCBI_API_KEY` or lower `RESEARCH_MAX_CALLS`
- Ensure API keys are set in `.env` before running features that require them

## License
MIT License

## Contact & references
- If using this project in research, please cite the project
- Contact: suttipong.kul@dome.tu.ac.th

Acknowledgements: CrewAI, PubMed/NCBI, Tavily, Thai FDA, and herbal centers for data and inspiration.