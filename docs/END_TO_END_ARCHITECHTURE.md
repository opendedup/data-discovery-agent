
# **End-to-End Architecture for an Agentic BI Generation System**

## **1\. Executive Summary**

This document outlines the comprehensive, end-to-end architecture for a sophisticated Agentic Business Intelligence (BI) system. The system is designed to transform a high-level, natural language business intent into a fully realized, interactive, and visually validated BI dashboard. This is achieved through a decomposable multi-agent system (MAS) where specialized AI agents collaborate in a structured workflow with critical human-in-the-loop validation points.

The architecture is built on a modern, scalable cloud-native stack, leveraging Google Cloud Platform (GCP) as its foundation. The agentic framework is powered by **Google's Agent Development Kit (ADK)** for the central orchestrator (Root Agent), with all agent services containerized and deployed on **Google Kubernetes Engine (GKE)**. A core principle of this design is the use of the **Model Context Protocol (MCP)** as the standard communication interface between the Root Agent and its sub-agents. This enables a modular, loosely coupled system where sub-agents can be developed independently and are reusable across different systems.1

**Core Technology Stack:**

* **Agent Framework:** Google's Agent Development Kit (ADK) for the Root Agent/Orchestrator.  
* **Cloud & Orchestration:** Google Cloud Platform (GCP), with agents running on Google Kubernetes Engine (GKE).  
* **Data Infrastructure:** Google BigQuery, Google Cloud Storage (GCS), Vertex AI Search.  
* **Data Governance:** Google Cloud Dataplex for automated and custom data lineage tracking.  
* **AI Models:** Google Gemini 2.5 Pro.  
* **API Layer:** Apollo GraphQL Server (Node.js).  
* **Presentation Layer:** Svelte and Apache ECharts.  
* **UI Validation:** Playwright with a Model Context Protocol (MCP) Server.  
* **Inter-Agent Communication:** Model Context Protocol (MCP).

This architecture represents a paradigm shift from traditional BI, moving from passive reporting to an active, collaborative analytics process. It addresses key challenges such as the maintainability of AI-generated code, data governance, and the management of long-running asynchronous tasks, creating a robust blueprint for a truly enterprise-ready agentic system.

## **2\. Architectural Philosophy: A Decomposable Multi-Agent System (MAS)**

The system is designed as a decomposable Multi-Agent System (MAS), a strategic choice that provides modularity, specialization, and scalability.4 Instead of a single monolithic agent, the workflow is broken down into a pipeline of specialized agents, each an expert in its domain. This approach mirrors a human data analytics team, with distinct roles for planning, data discovery, query engineering, and UI design.

The primary architectural patterns are:

* **Orchestrator Pattern:** A central **Root Agent**, built with Google's ADK, acts as the orchestrator or dispatcher. It manages the overall workflow, routes tasks to the appropriate sub-agent, and maintains the session state.  
* **Microservices-Inspired Design:** Each sub-agent is an independent, framework-agnostic service that communicates with the Root Agent exclusively over MCP. This loose coupling allows agents to be developed, deployed, and scaled independently and makes them reusable in other systems.  
* **Sequential Pipeline with HITL:** The workflow largely follows a sequential pipeline where the output of one agent becomes the input for the next. This pipeline is punctuated by **Human-in-the-Loop (HITL)** checkpoints, where a data scientist validates the agents' work before proceeding, ensuring accuracy and building trust.

## **3\. Foundational Infrastructure on Google Cloud Platform**

The entire system is built upon a production-ready infrastructure provisioned on GCP using a modular Terraform configuration. This ensures a secure, scalable, and repeatable environment.

```
┌─────────────────────────────────────────────────────────────┐
│                     GCP Project                              │
│                                                              │
│  ┌──────────────┐      ┌─────────────────┐                 │
│  │ Cloud        │      │ GKE Cluster     │ (optional)      │
│  │ Composer     │      │ - Workload ID   │                 │
│  │ (Airflow)    │      │ - Private Nodes │                 │
│  └──────┬───────┘      └────────┬────────┘                 │
│         │                       │                           │
│         │    ┌──────────────────┴─────────────┐            │
│         │    │                                 │            │
│  ┌──────▼────▼──────┐              ┌──────────▼─────────┐  │
│  │ Service Accounts  │              │ Artifact Registry  │  │
│  │ - Discovery (RO)  │              │ - Docker Images    │  │
│  │ - Metadata Writer │              └────────────────────┘  │
│  │ - GKE Node        │                                      │
│  │ - Composer        │                                      │
│  └──────┬────────────┘                                      │
│         │                                                   │
│  ┌──────▼─────────────────────────────────┐                │
│  │ GCS Buckets                             │                │
│  │ - JSONL files (Vertex AI Search input) │                │
│  │ - Reports (Human-readable docs)        │                │
│  └─────────────────────────────────────────┘                │
│                                                              │
│  Optional Modules:                                          │
│  ├─ Dataplex Profiling (data quality scans)                │
│  └─ Vertex AI Search (semantic search infrastructure)      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

* **Google Kubernetes Engine (GKE):** Serves as the primary compute environment. All agent services (the Root Agent and all sub-agents) are deployed as containerized workloads within a standard GKE cluster configured with private nodes and Workload Identity for secure, keyless access to other GCP services.  
* **Cloud Composer & Artifact Registry:** Cloud Composer (managed Airflow) is used to orchestrate scheduled background tasks, such as the data discovery and metadata ingestion pipeline. All container images for the agents are stored and managed in Artifact Registry.  
* **Vertex AI Search & GCS:** Vertex AI Search provides the core semantic search capability for the Data Discovery Agent. It is populated with metadata stored as JSONL files in a dedicated Google Cloud Storage (GCS) bucket.  
* **Dataplex:** Acts as the central data governance hub. It is used for automated data profiling and, critically, for tracking end-to-end data lineage from BigQuery through to the final BI report.

## **4\. End-to-End Agentic Workflow**

The workflow is divided into two primary phases: **Phase 1: Intent to Actionable Data** and **Phase 2: Data to Interactive Visualization**.

### **Phase 1: Intent to Actionable Data**

This phase translates a user's business goal into a validated, queryable, and governed semantic layer.

**Step 1 & 2: Intent Capture & Requirement Formulation**

* **Agent:** Planning Agent  
* **User:** Data Scientist  
* **Process:** The workflow begins with a collaborative dialogue between the data scientist and the Planning Agent. The user provides an initial intent (e.g., *"Provide the merchandising team at Costco insights into trending items in region 7"*). The agent asks clarifying questions to flesh out the scope.  
* **Output:** A structured **Product Requirement Prompt (PRP)**. This document is a **Markdown file**, a best practice that makes the prompt highly readable for humans and easily digestible for LLMs. It captures detailed requirements, business context, and key metrics, serving as the foundational artifact for subsequent agents.

**Step 3: Data Discovery**

* **Agent:** Data Discovery Agent  
* **Input:** The Markdown PRP.  
* **Process:** This agent finds the most relevant datasets to fulfill the PRP.  
  1. **Automated Metadata Ingestion (Background Process):** The agent's knowledge base is built by a continuously running process orchestrated by Cloud Composer. This process scans BigQuery, collecting schemas and statistics. It enriches this metadata using **Dataplex** for column profiling and **Gemini AI** to generate human-readable descriptions.  
  2. **Indexing for Search:** The enriched metadata is indexed into a **Vertex AI Search** datastore, creating a semantic search layer over the enterprise data catalog.  
  3. **Semantic Search:** The Data Discovery Agent uses the PRP to query the Vertex AI Search index and identify the most relevant data assets.  
* **Output:** A list of candidate BigQuery tables, complete with schemas and AI-generated documentation.

**Step 4: Query Generation & Validation**

* **Agent:** Query Generation Agent  
* **Input:** The PRP and the list of discovered datasets.  
* **Process:** This MCP service, powered by **Gemini 2.5 Pro**, creates and validates BigQuery SQL queries through a rigorous, iterative pipeline:  
  1. **Ideation:** Generates multiple candidate SQL queries.  
  2. **Validation:** Each query undergoes a multi-stage validation: syntax check, a BigQuery dry-run, and a sample execution.  
  3. **Alignment Check:** An LLM evaluates the sample results to score their alignment with the PRP's intent.  
  4. **Refinement:** If validation fails, the agent refines the query and retries, prioritizing accuracy over speed.  
* **Output:** An array of validated BigQuery SQL queries, each with a natural language description and an alignment score.

**Step 5: Semantic Layer & Data Lineage Generation**

* **Agent:** GraphQL Agent  
* **Input:** The validated BigQuery SQL queries.  
* **Process:** This agent automates the creation of the secure data access layer.  
  1. **API Generation:** It generates the TypeScript code for the **Apollo GraphQL Server**, creating typeDefs and resolvers that encapsulate the validated BigQuery queries.5  
  2. **Data Lineage Integration:** The agent integrates with **Google Cloud Dataplex** to provide end-to-end data lineage. For each resolver, it programmatically creates a custom lineage event using the Data Lineage API. This is optimized for performance: the static Process (the resolver logic) is registered on server startup, while the Lineage Event (linking the BigQuery source to the BI report target) is created asynchronously during the resolver's execution.  
* **Output:** An updated GraphQL schema with resolvers instrumented for full data lineage tracking.

**Step 6: Human-in-the-Loop (HITL) Data Validation**

* **User:** Data Scientist  
* **Process:** At this first major HITL checkpoint, the system prompts the user that the data is ready. The data scientist can now interact with the new GraphQL endpoints to preview the datasets and validate their correctness against the PRP.

### **Phase 2: Data to Interactive Visualization**

This phase transforms the validated data into an interactive dashboard, incorporating a second loop of planning, generation, and iteration.

**Step 7 & 8: Presentation Planning**

* **Agent:** Presentation Planning Agent  
* **User:** Data Scientist  
* **Process:** The user provides the visual intent (e.g., *"Show trending items as a bar chart"*). The agent engages in another collaborative dialogue to refine these requirements.  
* **Output:** A **UI Product Requirement Prompt (UI PRP)**, a separate Markdown file detailing the desired visual representations, layout, and interactive features.

**Step 9: UI Generation & Automated Validation**

* **Agent:** UI Generation Agent  
* **Input:** The Data PRP, the UI PRP, and the GraphQL API endpoint.  
* **Process:** This agent builds and validates the frontend dashboard.  
  1. **Code Generation:** The agent generates **Svelte** components that fetch data from the GraphQL API and render it using declarative **Apache ECharts** JSON configurations.5  
  2. **Iterative Validation Loop:** The agent uses a **Playwright MCP Server** for automated visual validation in a self-correcting feedback loop:  
     * The agent generates the Svelte/ECharts code.  
     * The MCP server renders the UI in a headless browser and provides the agent with a structured **accessibility snapshot** of the component, not a pixel-based image.  
     * The agent compares this structured output against the UI PRP. If there are discrepancies, it refines the code and repeats the process until the UI is validated.  
* **Output:** A functional and visually validated Svelte dashboard application.

**Step 10: Final User Review and Iteration**

* **Agent:** Root Agent (Orchestrator)  
* **User:** Data Scientist or Business User  
* **Process:** The final dashboard is presented to the user for iterative feedback (e.g., *"Change this to a line chart"*).  
  * **Intelligent Routing:** The **Root Agent**, built using Google's ADK, intercepts this feedback and analyzes the request's nature.  
  * **Stateful Handoff:** The Root Agent routes the task to the appropriate specialized sub-agent while preserving the current application state, ensuring progress is not lost. A UI change is routed to the **UI Generation Agent**, while a data change is routed back to the **Query Generation Agent**.  
* **Output:** An updated dashboard reflecting the user's feedback.

## **5\. Cross-Cutting Concerns and Advanced Patterns**

### **5.1. Asynchronous Communication for Long-Running Tasks**

To prevent the Root Agent from timing out while waiting for sub-agents like the Query or UI Generation agents, the system employs the **Asynchronous Request-Reply Pattern**.

* **Process:**  
  1. The Root Agent initiates a long-running task via an MCP call.  
  2. The sub-agent immediately acknowledges the request (e.g., with an HTTP 202 Accepted status) and returns a unique **Task ID** and a **Status URL**. The actual work is offloaded to a background process or message queue.  
  3. The Root Agent, using ADK's SessionService to manage state and a LoopAgent to manage the process, periodically polls the Status URL to check the job's status (PENDING, RUNNING, COMPLETED, FAILED).  
  4. Once the status is COMPLETED, the Root Agent retrieves the result and proceeds with the workflow.  
* **Benefit:** This decouples the agents, making the system resilient and preventing timeouts in a distributed environment. For extremely long or mission-critical tasks, this can be evolved into a full **Saga Pattern** implementation using a durable workflow engine.

### **5.2. AI-Generated Code Maintainability & Governance**

To address the significant risks of unmanaged AI-generated code—such as poor quality, security vulnerabilities, and lack of architectural context—this system implements a formal governance framework.6

* **Human-in-the-Loop (HITL) as a Core Principle:** All AI-generated code is treated as a "first draft" from a junior developer and is considered untrusted by default.  
* **Mandatory Human Code Reviews:** No AI-generated code is committed to the main branch without a thorough review by a senior human developer, checking for correctness, readability, security, and adherence to architectural patterns.  
* **Dedicated Refactoring Cycles:** Project sprints must explicitly allocate time for refactoring AI-generated code to pay down technical debt and ensure long-term sustainability.  
* **Automated Scanning:** The CI/CD pipeline must integrate static analysis security testing (SAST) and code quality tools to audit all code before deployment.10  
* **Governance through Lineage:** The integration with **Dataplex data lineage** provides a direct solution for data governance. When a dataset is deprecated, data engineering teams can use the lineage graph to perform impact analysis and identify exactly which BI reports and GraphQL resolvers are affected, enabling a managed and safe update process.

## **6\. Conclusion**

This end-to-end architecture represents a robust and forward-looking blueprint for building agentic BI systems. By leveraging a decomposable, multi-agent pipeline on a scalable GCP foundation, it successfully breaks down a highly complex problem into a series of manageable, specialized tasks. The integration of a standardized communication protocol (MCP), asynchronous patterns for long-running jobs, automated validation with Playwright, comprehensive data governance with Dataplex, and critical human-in-the-loop checkpoints ensures that the final output is not only functional but also accurate, trustworthy, and maintainable. This system moves beyond simple code generation to create a dynamic, collaborative partnership between human experts and a team of specialized AI agents.

#### **Works cited**

1. How to handle slow resolver performance in Apollo Server with large datasets?, accessed October 21, 2025, [https://community.apollographql.com/t/how-to-handle-slow-resolver-performance-in-apollo-server-with-large-datasets/9383](https://community.apollographql.com/t/how-to-handle-slow-resolver-performance-in-apollo-server-with-large-datasets/9383)  
2. Apollo server caching : Getting it right \! | by Prabhakar Pratim Borah | Medium, accessed October 21, 2025, [https://prabhakar-borah.medium.com/apollo-server-caching-getting-it-right-76e3dcd200c4](https://prabhakar-borah.medium.com/apollo-server-caching-getting-it-right-76e3dcd200c4)  
3. Caching in Apollo Router \- Apollo GraphQL Docs, accessed October 21, 2025, [https://www.apollographql.com/docs/graphos/routing/performance/caching](https://www.apollographql.com/docs/graphos/routing/performance/caching)  
4. GraphQL vs REST: What's the Difference? | IBM, accessed October 21, 2025, [https://www.ibm.com/think/topics/graphql-vs-rest-api](https://www.ibm.com/think/topics/graphql-vs-rest-api)  
5. System Architecture: AI-Powered BI Dashboard Gener...  
6. The Hidden Risks of AI Code Generation: What Every Developer Should Know \- Flux, accessed October 21, 2025, [https://www.askflux.ai/blog/the-hidden-risks-of-ai-code-generation-what-every-developer-should-know](https://www.askflux.ai/blog/the-hidden-risks-of-ai-code-generation-what-every-developer-should-know)  
7. Managing Risk from AI Generated Code \- Trigyn Technologies, accessed October 21, 2025, [https://www.trigyn.com/insights/managing-risks-ai-generated-code](https://www.trigyn.com/insights/managing-risks-ai-generated-code)  
8. www.turintech.ai, accessed October 21, 2025, [https://www.turintech.ai/blog/the-hidden-cost-of-ai-generated-code-what-research-and-industry-trends-are-revealing\#:\~:text=Security%20%26%20Maintainability%20Risks%20%E2%80%93%20AI%2D,best%20practices%2C%20or%20compliance%20requirements.](https://www.turintech.ai/blog/the-hidden-cost-of-ai-generated-code-what-research-and-industry-trends-are-revealing#:~:text=Security%20%26%20Maintainability%20Risks%20%E2%80%93%20AI%2D,best%20practices%2C%20or%20compliance%20requirements.)  
9. Zero Human Code \-What I learned from forcing AI to build (and fix) its own code for 27 straight days | by Daniel Bentes | Medium, accessed October 21, 2025, [https://medium.com/@danielbentes/zero-human-code-what-i-learned-from-forcing-ai-to-build-and-fix-its-own-code-for-27-straight-0c7afec363cb](https://medium.com/@danielbentes/zero-human-code-what-i-learned-from-forcing-ai-to-build-and-fix-its-own-code-for-27-straight-0c7afec363cb)  
10. GraphQL Security Best Practices \- StackHawk, accessed October 21, 2025, [https://www.stackhawk.com/blog/graphql-security/](https://www.stackhawk.com/blog/graphql-security/)  
11. Announcing a New Framework for Securing AI-Generated Code \- Cisco Blogs, accessed October 21, 2025, [https://blogs.cisco.com/ai/announcing-new-framework-securing-ai-generated-code](https://blogs.cisco.com/ai/announcing-new-framework-securing-ai-generated-code)