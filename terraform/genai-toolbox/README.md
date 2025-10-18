# GenAI Toolbox Deployment - Phase 0.2

This directory contains Terraform configuration for deploying Google's GenAI Toolbox to GKE with pre-configured tools for BigQuery and Dataplex.

## Overview

GenAI Toolbox provides pre-built, production-ready tools for interacting with GCP data sources:
- **BigQuery Tools**: Get table metadata, execute read-only queries
- **Dataplex Tools**: Retrieve lineage, data quality, and profiling information  
- **MCP Protocol**: Model Context Protocol for agent communication

## Architecture

```
┌─────────────────────────────────────────────────────┐
│          Data Discovery Agents (Future)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Schema   │  │ Lineage  │  │ Quality  │          │
│  │ Indexer  │  │ Indexer  │  │ Indexer  │          │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
└───────┼─────────────┼─────────────┼─────────────────┘
        │             │             │
        └─────────────┴─────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   GenAI Toolbox Service     │
        │   (Internal LoadBalancer)   │
        │                             │
        │   MCP Protocol: Port 8080   │
        │   Health: Port 8081         │
        └──────────┬──────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
┌───────────────┐    ┌────────────────┐
│   BigQuery    │    │    Dataplex    │
│     Tools     │    │     Tools      │
└───────────────┘    └────────────────┘
```

## Prerequisites

1. GKE cluster is running (Phase 0.1 complete)
2. Workload Identity is configured
3. Service accounts have correct permissions:
   - `data-discovery-agent`: BigQuery, Dataplex, Data Catalog access

## Configuration

### Main Configuration File

`config/genai-toolbox/toolbox-config.yaml` contains:

- **Security Settings**: Read-only mode enforcement (SR-2A compliance)
- **BigQuery Tools**: `bigquery-get-table-info`, `bigquery-execute-sql`
- **Dataplex Tools**: Lineage, data quality, profiling
- **MCP Protocol**: Endpoint configuration
- **Connection Settings**: Timeouts, retries, pooling

### Key Security Features

✅ **Read-Only Mode**: All tools are configured for read-only operations  
✅ **Query Validation**: Blocks DDL/DML statements (CREATE, INSERT, UPDATE, DELETE)  
✅ **Allowed Operations**: Only SELECT, DESCRIBE, SHOW, EXPLAIN  
✅ **Audit Logging**: All queries are logged  
✅ **Workload Identity**: No service account keys stored

## Deployment

### Option 1: Via Parent Terraform Module

The GenAI Toolbox will be deployed when you apply the main Terraform configuration:

```bash
cd /home/user/git/data-discovery-agent/terraform
terraform apply
```

### Option 2: Deploy Separately

```bash
cd /home/user/git/data-discovery-agent/terraform/genai-toolbox
terraform init
terraform plan -var="project_id=lennyisagoodboy" -var="region=us-central1" -var="cluster_name=data-discovery-cluster"
terraform apply
```

## Resources Created

| Resource | Type | Purpose |
|----------|------|---------|
| `genai-toolbox` | Deployment | Runs GenAI Toolbox pods (2 replicas) |
| `genai-toolbox` | Service | Internal LoadBalancer for MCP protocol |
| `genai-toolbox-config` | ConfigMap | Tool configuration |
| `genai-toolbox` | HPA | Auto-scaling (2-10 pods) |
| `genai-toolbox` | NetworkPolicy | Network security rules |

## Endpoints

After deployment:

- **MCP Protocol**: `http://genai-toolbox.data-discovery.svc.cluster.local:8080/mcp`
- **Health Check**: `http://genai-toolbox.data-discovery.svc.cluster.local:8081/health`
- **Metrics**: `http://genai-toolbox.data-discovery.svc.cluster.local:8080/metrics`

## Testing

### 1. Check Deployment Status

```bash
kubectl get pods -n data-discovery -l app=genai-toolbox
kubectl get svc -n data-discovery genai-toolbox
```

### 2. Check Health

```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n data-discovery -- \
  curl http://genai-toolbox.data-discovery.svc.cluster.local:8081/health
```

### 3. Test MCP Endpoint

```bash
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n data-discovery -- \
  curl -X POST http://genai-toolbox.data-discovery.svc.cluster.local:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"tool": "bigquery-get-table-info", "parameters": {"table": "project.dataset.table"}}'
```

### 4. View Logs

```bash
kubectl logs -n data-discovery -l app=genai-toolbox --tail=100 -f
```

## Configuration Updates

To update the GenAI Toolbox configuration:

1. Edit `config/genai-toolbox/toolbox-config.yaml`
2. Apply changes:
   ```bash
   terraform apply
   ```
3. Rollout restart:
   ```bash
   kubectl rollout restart deployment/genai-toolbox -n data-discovery
   ```

## Scaling

### Manual Scaling

```bash
kubectl scale deployment genai-toolbox -n data-discovery --replicas=5
```

### Auto-Scaling

HPA is configured to scale between 2-10 pods based on:
- CPU utilization: 70%
- Memory utilization: 80%

## Monitoring

### Metrics

GenAI Toolbox exposes Prometheus metrics at `/metrics`:

- Request count
- Request duration
- Error rate
- Tool usage statistics

### Logs

All queries and operations are logged with:
- Timestamp
- User/service account
- Tool used
- Query/operation details
- Success/failure status

## Security

### SR-2A Compliance Checklist

- [x] Read-only mode enforced
- [x] No DDL/DML operations allowed
- [x] Query validation enabled
- [x] Workload Identity (no keys)
- [x] Audit logging enabled
- [x] Network policies in place
- [x] Resource limits set
- [x] Non-root user
- [x] Read-only filesystem

### Network Security

- **Ingress**: Only from `data-discovery` namespace
- **Egress**: Only to GCP APIs (443) and DNS (53)
- **Service**: Internal LoadBalancer (no external access)

## Troubleshooting

### Pods Not Starting

```bash
kubectl describe pods -n data-discovery -l app=genai-toolbox
kubectl logs -n data-discovery -l app=genai-toolbox
```

Common issues:
- ConfigMap not mounted: Check `kubectl get cm -n data-discovery`
- Workload Identity not configured: Check service account annotations
- Image pull errors: Verify image name/tag

### Health Check Failing

```bash
kubectl exec -it -n data-discovery $(kubectl get pod -n data-discovery -l app=genai-toolbox -o jsonpath='{.items[0].metadata.name}') -- wget -O- http://localhost:8081/health
```

### Permission Errors

Check service account permissions:
```bash
gcloud projects get-iam-policy lennyisagoodboy \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:data-discovery-agent@lennyisagoodboy.iam.gserviceaccount.com"
```

Required roles:
- `roles/bigquery.metadataViewer`
- `roles/bigquery.jobUser`
- `roles/dataplex.viewer`
- `roles/dataplex.metadataReader`

## Cost

Estimated monthly cost for GenAI Toolbox:

- **Compute**: 2x pods @ 250m CPU, 512Mi RAM ≈ $5-10/month
- **Load Balancer**: Internal LB ≈ $20/month
- **Storage**: Negligible (config only)

**Total**: ~$25-30/month for base deployment

Auto-scaling can increase costs during high usage periods.

## Next Steps

After GenAI Toolbox is deployed:

1. **Phase 1**: Implement Vertex AI Search infrastructure
2. **Phase 2**: Create background discovery agents that use these tools
3. **Phase 3**: Create live query agents
4. **Phase 4**: Implement Smart Query Router

## Support

- Configuration issues: Check `toolbox-config.yaml`
- Deployment issues: Check Terraform logs
- Runtime issues: Check pod logs
- Tool errors: Review audit logs in Cloud Logging

## References

- [GenAI Toolbox Documentation](https://cloud.google.com/genai-toolbox)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Workload Identity](https://cloud.google.com/kubernetes-engine/docs/how-to/workload-identity)

