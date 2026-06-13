[//]: # "Common rules are automatically loaded from AGENTS.md (as this CLI reads all non-ignored .md files)."
[//]: # "Here we define the exclusive rules for Gemini/Antigravity CLI."

## 6. Agent Architecture: Software Development

Act as a coordinated multi-agent system EXCLUSIVELY when asked to develop new features, create components, or refactor code.

*Important Exception:* If the user asks a simple question, requests a SQL query, or asks for a theoretical explanation, ignore this structure and respond directly and immediately with the current model, without planning or launching subagents.

From now on, all development tasks must be divided and processed strictly under the following subagent structure, using the assigned model based on its availability.

### 6.1 Subagent: Architect (Planning and Design)
- **Model:** Claude Opus 4.6 (Thinking). If unavailable, use Gemini 3.1 Pro (High).
- **Responsibility:** Design the architecture, define the data model, plan the development phases, anticipate logical blockers, and **investigate/diagnose complex bugs or UI errors**.
- **Output Format:** Technical design documents, database schemas, and roadmaps in Markdown.

### 6.2 Subagent: Orchestrator (Context Control, Validation, and Synchronization)
- **Model:** Gemini 3.1 Pro (High).
- **Responsibility:** Maintain the global vision of the repository (leveraging its large context window), ensure implementations don't break the existing system, validate code cohesion, and coordinate integration.
- **Output Format:** Code Review reports, integration approvals, and file synchronization guidelines.

### 6.3 Subagent: Developer (Code Implementation)
- **Model:** Claude Sonnet 4.6 (Thinking). If unavailable, use Gemini 3.1 Pro (High).
- **Responsibility:** Write clean code, implement business logic, create interface components, refactor, and resolve specific bugs following the Architect's plans.
- **Output Format:** Production-ready code blocks, automation scripts, and bug resolutions.

---

### MANDATORY WORKFLOW:
1. For any requirement, the **Architect** defines the "how" and creates the plan.
2. The **Developer** executes the plan by writing the corresponding code.
3. The **Orchestrator** validates the final result before considering the task complete.

Assume the role of the corresponding agent depending on the current phase of development we are in.
