# Phase 7: Frontend Deployment (Cloud Run + Cloud CDN)

## Overview

This guide deploys the NextJS React frontend on GCP using Cloud Run, which is equivalent to AWS App Runner + CloudFront.

## AWS vs GCP Comparison

| AWS Service | GCP Equivalent |
|-------------|----------------|
| App Runner | Cloud Run |
| CloudFront | Cloud CDN + Cloud Load Balancing |
| Route 53 | Cloud DNS |
| ACM (SSL Certs) | Certificate Manager |
| S3 (Static Assets) | Cloud Storage |

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Internet                                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              Cloud Load Balancer (HTTPS)                     │
│                   + Cloud CDN                                │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    Cloud Run (Frontend)                      │
│                      NextJS App                              │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                  Cloud Run (Backend API)                     │
│                     Orchestrator                             │
└──────────────────────────────────────────────────────────────┘
```

## Steps

### Step 1: Build Frontend Container

```bash
# Navigate to frontend directory
cd frontend

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

ENV PORT=8080
EXPOSE 8080

CMD ["node", "server.js"]
EOF

# Build and push
export PROJECT_ID="your-project-id"
export REGION="us-central1"

docker build -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/alex-containers/frontend:latest .
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/alex-containers/frontend:latest
```

### Step 2: Configure NextJS for Standalone

Update `next.config.js`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY,
  },
}

module.exports = nextConfig
```

### Step 3: Deploy Terraform

```bash
cd terraform/7_frontend/
terraform init
terraform plan
terraform apply
```

### Step 4: Configure Clerk Authentication

1. Get your Clerk keys from dashboard.clerk.com
2. Store in Secret Manager:

```bash
gcloud secrets create clerk-publishable-key --data-file=- << EOF
pk_live_xxx
EOF

gcloud secrets create clerk-secret-key --data-file=- << EOF
sk_live_xxx
EOF
```

### Step 5: Set Up Custom Domain (Optional)

1. Verify domain ownership in Cloud DNS
2. Create managed SSL certificate
3. Configure load balancer with domain

```bash
# Add DNS record
gcloud dns record-sets create yourdomain.com \
  --zone=your-zone \
  --type=A \
  --ttl=300 \
  --rrdatas=LOAD_BALANCER_IP
```

## Environment Variables

The frontend needs these environment variables:

| Variable | Description |
|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend orchestrator URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk public key |
| `CLERK_SECRET_KEY` | Clerk secret key |

## Vercel Alternative

If you prefer Vercel for frontend (as mentioned in the course):

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel --prod

# Set environment variables
vercel env add NEXT_PUBLIC_API_URL production
vercel env add NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY production
```

For Vercel + GCP backend:
1. Deploy frontend to Vercel
2. Keep backend on GCP Cloud Run
3. Configure CORS on backend

```python
# backend/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Performance Optimization

### Enable Cloud CDN

```hcl
# In terraform
resource "google_compute_backend_service" "frontend" {
  enable_cdn = true
  
  cdn_policy {
    cache_mode = "CACHE_ALL_STATIC"
    default_ttl = 3600
    max_ttl     = 86400
  }
}
```

### Configure Cache Headers in NextJS

```javascript
// next.config.js
async headers() {
  return [
    {
      source: '/_next/static/:path*',
      headers: [
        {
          key: 'Cache-Control',
          value: 'public, max-age=31536000, immutable',
        },
      ],
    },
  ]
}
```

## Monitoring

```bash
# View frontend logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=frontend" --limit=50

# Check latency metrics
gcloud monitoring metrics list --filter="metric.type:cloudrun"
```

## Troubleshooting

### Build Failures
- Check Node version compatibility
- Verify all dependencies are in package.json
- Check for missing environment variables

### Runtime Errors
- Check Cloud Run logs
- Verify API URL is correct
- Check Clerk configuration

### Performance Issues
- Enable Cloud CDN
- Optimize images with `next/image`
- Use React Server Components where possible

## Next Steps

After deploying frontend, proceed to [8_enterprise.md](8_enterprise.md) for enterprise features.
