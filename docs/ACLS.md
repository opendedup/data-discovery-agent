# Access Control Lists (ACLs) - Data Discovery Agent

This document describes all service accounts, their IAM permissions, and the justification for each permission following the principle of least privilege.

## Table of Contents

- [Service Accounts Overview](#service-accounts-overview)
- [1. Cloud Composer Service Account](#1-cloud-composer-service-account)
- [2. Discovery Service Account](#2-discovery-service-account)
- [3. Metadata Write Service Account](#3-metadata-write-service-account)
- [4. GKE Service Account](#4-gke-service-account)
- [Security Principles](#security-principles)
- [Permission Audit Log](#permission-audit-log)

---

## Service Accounts Overview

| Service Account | Purpose | Scope | Used By |
|----------------|---------|-------|---------|
| `data-discovery-composer@` | Run Airflow DAGs for orchestration | Project-wide read, specific write | Cloud Composer |
| `data-discovery-agent@` | Read-only data discovery operations | Project-wide read-only | GKE Pods |
| `data-discovery-metadata@` | Write enriched metadata to Data Catalog | Data Catalog only | GKE Pods |
| `data-discovery-gke@` | GKE node operations | Minimal logging/monitoring | GKE Nodes |

---

## 1. Cloud Composer Service Account

**Email**: `data-discovery-composer@{project}.iam.gserviceaccount.com`

**Purpose**: Executes Airflow DAGs that orchestrate the metadata collection, profiling, and indexing pipeline.

### IAM Roles

#### Core Composer Permissions

| Role | Justification |
|------|---------------|
| `roles/composer.worker` | **Required** for Cloud Composer environment operations. Allows the service account to execute DAG tasks and manage Airflow worker processes. |
| `roles/logging.logWriter` | Write logs from Airflow tasks to Cloud Logging for monitoring and debugging. |
| `roles/monitoring.metricWriter` | Write custom metrics from DAG executions to Cloud Monitoring for observability. |

#### BigQuery Permissions

| Role | Justification |
|------|---------------|
| `roles/bigquery.metadataViewer` | **Read** schema information, table metadata, and dataset properties from **all** BigQuery datasets in the project. Essential for metadata discovery. |
| `roles/bigquery.dataViewer` | **Query actual table data** for SQL-based profiling when Dataplex profiling is not available. Used to calculate min/max/distinct values and sample data for enrichment. Limited to sampling (typically LIMIT 10000). |
| `roles/bigquery.dataEditor` | **Write** discovered metadata to the `data_discovery.discovered_assets` BigQuery table. Also create the dataset/table if it doesn't exist. |
| `roles/bigquery.jobUser` | **Run** BigQuery query jobs for data profiling and metadata extraction. Required to execute SELECT queries. |

#### Google Cloud Storage Permissions

| Role | Resource | Justification |
|------|----------|---------------|
| `roles/storage.objectAdmin` | `{project}-data-discovery-jsonl` bucket | Read/write JSONL files for Vertex AI Search ingestion. DAGs write formatted metadata as JSONL and trigger imports. |
| `roles/storage.objectAdmin` | `{project}-data-discovery-reports` bucket | Read/write human-readable Markdown reports about discovered data assets. |

**Note**: Bucket-specific permissions (not project-wide) for security isolation.

#### Vertex AI Search Permissions

| Role | Justification |
|------|---------------|
| `roles/aiplatform.user` | Access Vertex AI Platform services. Required for AI Platform operations. |
| `roles/discoveryengine.editor` | **Import documents** from BigQuery directly into Vertex AI Search datastore. Used by the `import_to_vertex_ai_task` DAG task to trigger document ingestion. Grants `discoveryengine.documents.import` permission. |

#### Data Catalog Permissions

| Role | Justification |
|------|---------------|
| `roles/datacatalog.viewer` | Read metadata, lineage, and tags from Data Catalog. Used to enrich discovered metadata with existing catalog information. |

#### DLP Permissions

| Role | Justification |
|------|---------------|
| `roles/dlp.reader` | Read DLP inspection results for PII detection. Optional: used if DLP scans are integrated into the discovery pipeline. |

#### Dataplex Permissions

| Role | Justification |
|------|---------------|
| `roles/dataplex.viewer` | Read existing Dataplex metadata, data quality results, and lineage information. |
| `roles/dataplex.dataScanAdmin` | **Create and run** data profile scans for comprehensive table profiling. Enables automated profiling of discovered tables using Dataplex's native capabilities (statistics, PII detection, data quality metrics). |

#### Data Lineage Permissions

| Role | Justification |
|------|---------------|
| `roles/datalineage.admin` | **Record data lineage** for BigQuery writes and GCS exports. Tracks data provenance by creating lineage processes, runs, and events in Data Catalog Lineage API. Essential for understanding data flow from source tables → discovered_assets table → markdown reports. |

### Security Considerations

- **No DELETE permissions**: Cannot delete BigQuery tables, datasets, or GCS objects
- **No Schema Modification**: Cannot ALTER tables or change BigQuery schemas
- **Read-only on source data**: Only writes to dedicated discovery tables/buckets
- **Scoped Storage Access**: Only has access to specific discovery buckets, not all project storage

---

## 2. Discovery Service Account (Read-Only)

**Email**: `data-discovery-agent@{project}.iam.gserviceaccount.com`

**Purpose**: Read-only service account for GKE-based data discovery operations (SR-2A compliant).

### IAM Roles

| Role | Justification |
|------|---------------|
| `roles/bigquery.metadataViewer` | Read BigQuery metadata (schemas, table properties) for discovery. **Read-only**, cannot query actual data. |
| `roles/bigquery.jobUser` | Required to run metadata queries (e.g., `INFORMATION_SCHEMA` queries). |
| `roles/datacatalog.viewer` | Read Data Catalog entries, tags, and lineage for metadata enrichment. |
| `roles/logging.viewer` | Read Cloud Logging audit logs to understand data access patterns. |
| `roles/logging.privateLogViewer` | Read private/security logs for audit trail analysis. |
| `roles/dlp.reader` | Read DLP inspection results for PII classification. |
| `roles/aiplatform.user` | Query Vertex AI Search for existing indexed data. |
| `roles/dataplex.viewer` | Read Dataplex data quality and profiling results. |
| `roles/dataplex.metadataReader` | Read Dataplex metadata about data assets. |

### Storage Permissions (Bucket-Specific)

| Role | Resource | Justification |
|------|----------|---------------|
| `roles/storage.objectCreator` | JSONL bucket | Write discovered metadata as JSONL files for Vertex AI Search. |
| `roles/storage.objectCreator` | Reports bucket | Write generated Markdown reports. |

### Workload Identity Binding

Kubernetes service account `discovery-agent` in namespace `data-discovery` can impersonate this GCP service account.

### Security Considerations

- **Strictly read-only** for source data
- **Cannot modify** BigQuery tables or schemas
- **Cannot delete** any resources
- **Limited write** only to designated discovery output buckets

---

## 3. Metadata Write Service Account

**Email**: `data-discovery-metadata@{project}.iam.gserviceaccount.com`

**Purpose**: Limited write permissions for enriching metadata in Data Catalog only.

### IAM Roles

| Role | Justification |
|------|---------------|
| `roles/datacatalog.entryGroupOwner` | Create and manage Data Catalog entry groups for organizing discovered metadata. Can create entries, tag templates, and tags. |
| `roles/datacatalog.viewer` | Read existing catalog entries for verification and enrichment. |
| `roles/logging.logWriter` | Write audit logs for metadata write operations. |

### Workload Identity Binding

Kubernetes service account `metadata-writer` in namespace `data-discovery` can impersonate this GCP service account.

### Security Considerations

- **Data Catalog only**: No access to BigQuery, GCS, or other data sources
- **Cannot read/write actual data**: Only manages metadata entries
- **Audit trail**: All writes are logged to Cloud Logging

---

## 4. GKE Service Account

**Email**: `data-discovery-gke@{project}.iam.gserviceaccount.com`

**Purpose**: Minimal permissions for GKE cluster node operations.

### IAM Roles

| Role | Justification |
|------|---------------|
| `roles/logging.logWriter` | Write node and container logs to Cloud Logging. |
| `roles/monitoring.metricWriter` | Write node and container metrics to Cloud Monitoring. |
| `roles/monitoring.viewer` | Read monitoring data for node health checks. |

### Security Considerations

- **Minimal node permissions**: Only logging and monitoring
- **No data access**: Cannot access BigQuery, GCS, or other services
- **Pods use Workload Identity**: Application pods use separate service accounts

---

## Security Principles

### 1. Principle of Least Privilege

Every service account is granted **only** the permissions necessary for its specific function. No service account has project-wide admin or owner permissions.

### 2. Separation of Duties

- **Discovery** (read-only) vs **Metadata Write** (write to catalog only)
- **Composer** (orchestration) vs **Application** (execution)
- **GKE Nodes** (infrastructure) vs **Pods** (applications)

### 3. Defense in Depth

- **Workload Identity**: GKE pods impersonate GCP service accounts (no key files)
- **Bucket-level IAM**: Storage permissions scoped to specific buckets
- **Read-only by default**: Only designated services can write to discovery outputs
- **Audit logging**: All operations logged to Cloud Logging

### 4. Data Protection

- **No data deletion capabilities**: Service accounts cannot delete source data
- **No schema modifications**: Cannot ALTER tables or change schemas
- **Read-only access to source data**: Discovery operations don't modify originals
- **Dedicated output locations**: All writes go to specific discovery buckets/tables

### 5. SR-2A Compliance

The discovery service account (`data-discovery-agent@`) is **read-only** for sensitive data:
- Cannot modify BigQuery tables
- Cannot delete or alter data
- Can only write to designated discovery output locations
- All access is logged and auditable

---

## Permission Audit Log

| Date | Service Account | Change | Justification | Changed By |
|------|----------------|--------|---------------|------------|
| 2025-10-20 | `data-discovery-composer@` | Added `roles/discoveryengine.editor` | Import documents directly from BigQuery to Vertex AI Search datastore (bypassing JSONL) | Terraform |
| 2025-10-20 | `data-discovery-composer@` | Added `roles/datalineage.admin` | Track data lineage for BigQuery writes and GCS exports using Data Catalog Lineage API | Terraform |
| 2025-01-19 | `data-discovery-composer@` | Added `roles/bigquery.dataViewer` | SQL-based profiling requires reading table data for min/max/distinct calculations when Dataplex unavailable | Terraform |
| 2025-01-19 | `data-discovery-composer@` | Added `roles/dataplex.dataScanAdmin` | Enable automated creation of Dataplex data profile scans for discovered tables | Terraform |
| 2025-01-19 | All SAs | Initial creation | Bootstrap data discovery infrastructure | Terraform |

---

## Reviewing and Updating Permissions

### When to Review

- **Quarterly**: Regular security audit of all service account permissions
- **After incidents**: Review after any security incident or unauthorized access
- **Feature additions**: When adding new discovery capabilities
- **Compliance audits**: Before compliance certification reviews

### Review Checklist

- [ ] Are all permissions still necessary?
- [ ] Can any permissions be further restricted?
- [ ] Are there unused permissions that can be removed?
- [ ] Do new features require additional permissions?
- [ ] Are all permissions documented with justification?
- [ ] Are audit logs being monitored?

### Requesting Permission Changes

1. Document the business justification
2. Specify the exact role/permission needed
3. Explain why current permissions are insufficient
4. Get security team approval
5. Update Terraform configuration
6. Update this ACLS.md document
7. Add entry to Permission Audit Log

---

## References

- [Google Cloud IAM Roles](https://cloud.google.com/iam/docs/understanding-roles)
- [BigQuery IAM Roles](https://cloud.google.com/bigquery/docs/access-control)
- [Workload Identity Best Practices](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)
- [Cloud Composer Service Accounts](https://cloud.google.com/composer/docs/composer-2/access-control#service-account)
- [Dataplex IAM Roles](https://cloud.google.com/dataplex/docs/iam-roles)

---

**Last Updated**: October 20, 2025  
**Maintained By**: Infrastructure Team  
**Review Cycle**: Quarterly

