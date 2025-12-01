# Destroy Script Usage

The `destroy.ps1` script safely destroys all or selected parts of the Alex Multi-Agent SaaS deployment on GCP.

## Basic Usage

### Destroy Everything (Full Teardown)

```powershell
.\scripts\destroy.ps1
```

This will destroy all resources in reverse order:
1. Frontend (7_frontend)
2. Agents (6_agents)
3. Database (5_database)
4. Pub/Sub (3_pubsub)
5. Vertex AI (2_vertex_ai)
6. Permissions (1_permissions)

### Destroy Specific Phases

```powershell
# Destroy only frontend
.\scripts\destroy.ps1 -DestroyFrontend -DestroyAll:$false

# Destroy only agents
.\scripts\destroy.ps1 -DestroyAgents -DestroyAll:$false

# Destroy database (biggest cost savings)
.\scripts\destroy.ps1 -DestroyDatabase -DestroyAll:$false

# Destroy multiple phases
.\scripts\destroy.ps1 -DestroyFrontend -DestroyAgents -DestroyAll:$false
```

### Skip Confirmation Prompt

```powershell
.\scripts\destroy.ps1 -SkipConfirmation
```

### Destroy Secrets Too

```powershell
.\scripts\destroy.ps1 -DestroySecrets
```

This will also delete:
- `alex-db-password`
- `polygon-api-key`
- `openai-api-key`
- `clerk-publishable-key`
- `clerk-secret-key`

**Warning**: Only use this if you're completely tearing down the deployment. You'll need to recreate secrets if you redeploy.

## Examples

### Quick Cost Savings (Destroy Database)

```powershell
# Destroy database when not actively working (saves ~$30-100/month)
.\scripts\destroy.ps1 -DestroyDatabase -DestroyAll:$false
```

### Complete Cleanup

```powershell
# Destroy everything including secrets
.\scripts\destroy.ps1 -DestroySecrets -SkipConfirmation
```

### Partial Cleanup (Keep Database)

```powershell
# Destroy frontend and agents, keep database
.\scripts\destroy.ps1 -DestroyFrontend -DestroyAgents -DestroyAll:$false
```

## Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `-ProjectId` | GCP Project ID (auto-detected from .env or gcloud config) | Auto |
| `-Region` | GCP Region | `us-central1` |
| `-SkipConfirmation` | Skip the confirmation prompt | `$false` |
| `-DestroySecrets` | Also destroy Secret Manager secrets | `$false` |
| `-DestroyAll` | Destroy all phases | `$true` |
| `-DestroyFrontend` | Destroy frontend only | `$false` |
| `-DestroyAgents` | Destroy agents only | `$false` |
| `-DestroyDatabase` | Destroy database only | `$false` |
| `-DestroyPubSub` | Destroy Pub/Sub only | `$false` |
| `-DestroyVertexAI` | Destroy Vertex AI only | `$false` |
| `-DestroyPermissions` | Destroy permissions only | `$false` |

## Important Notes

1. **Database Destruction**: The database is the most expensive resource. Destroy it when not actively working to save costs.

2. **Dependencies**: The script destroys in reverse order to handle dependencies. If you destroy a phase manually, you may need to destroy dependent phases first.

3. **State Files**: Terraform state files are kept locally. If you lose them, you may need to manually clean up resources in the GCP Console.

4. **Secrets**: Only destroy secrets if you're completely removing the deployment. You'll need to recreate them for redeployment.

5. **Deletion Protection**: Production databases may have deletion protection enabled. You'll need to disable it first in the GCP Console.

## Troubleshooting

### Terraform State Lock

If you get a state lock error:
```powershell
# Manually unlock (use with caution)
cd terraform/[phase]
terraform force-unlock [LOCK_ID]
```

### Resources Not Destroying

Some resources may have dependencies. Check the GCP Console for:
- Cloud Run services that depend on the database
- Pub/Sub subscriptions that depend on Cloud Run services
- IAM bindings that depend on service accounts

### Manual Cleanup

If the script fails, you can manually destroy resources:
```powershell
cd terraform/[phase]
terraform destroy
```

Or use gcloud commands:
```powershell
# List Cloud Run services
gcloud run services list --project=PROJECT_ID

# Delete a service
gcloud run services delete SERVICE_NAME --region=REGION --project=PROJECT_ID
```

