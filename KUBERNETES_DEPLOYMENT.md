# PAAIM Kubernetes Deployment Guide

## Prerequisites

- Kubernetes cluster 1.20+
- Helm 3.0+
- kubectl configured
- Docker registry access

## Quick Start

### 1. Install Dependencies

```bash
# Add Bitnami Helm repository
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo update

# Create namespace
kubectl create namespace paaim
kubectl config set-context --current --namespace=paaim
```

### 2. Create Secrets

```bash
# Create secrets for production credentials
kubectl create secret generic paaim-secrets \
  --from-literal=jwt-secret-key=$(openssl rand -hex 32) \
  --from-literal=anthropic-api-key=$ANTHROPIC_API_KEY \
  --from-literal=postgres-password=$(openssl rand -hex 16) \
  --from-literal=mes-password=secure_password \
  --from-literal=cmms-password=secure_password
```

### 3. Deploy PAAIM

```bash
# Using Helm
helm install paaim ./helm-chart \
  --namespace paaim \
  --values ./helm-chart/values.yaml \
  --values ./helm-chart/values-production.yaml

# Or upgrade existing deployment
helm upgrade paaim ./helm-chart \
  --namespace paaim \
  --values ./helm-chart/values-production.yaml
```

### 4. Verify Deployment

```bash
# Check pods
kubectl get pods -n paaim

# Check services
kubectl get svc -n paaim

# View logs
kubectl logs -n paaim deployment/paaim-api -f

# Port forward for local testing
kubectl port-forward -n paaim svc/paaim-api 8000:80
```

## Configuration

### Production Values (values-prod.yaml)

```yaml
replicaCount: 5
image:
  tag: "0.1.0-prod"

resources:
  limits:
    cpu: 2000m
    memory: 1Gi
  requests:
    cpu: 1000m
    memory: 512Mi

autoscaling:
  minReplicas: 5
  maxReplicas: 20

postgresql:
  primary:
    persistence:
      size: 100Gi

redis:
  master:
    persistence:
      size: 50Gi

securityContext:
  runAsNonRoot: true
  fsReadOnlyRootFilesystem: true
```

### Staging Values (values-staging.yaml)

```yaml
replicaCount: 2
image:
  tag: "0.1.0-staging"

resources:
  limits:
    cpu: 1000m
    memory: 512Mi

autoscaling:
  minReplicas: 2
  maxReplicas: 5
```

## Production Features

### High Availability
- Multi-replica deployments
- Pod anti-affinity rules
- Health checks (liveness, readiness)
- Graceful termination (30s timeout)

### Scaling
- Horizontal Pod Autoscaler (HPA)
- CPU/Memory-based scaling
- Pod Disruption Budgets (PDB)

### Monitoring
- Prometheus metrics endpoint
- Health check endpoints
- Service monitoring

### Security
- Non-root containers
- Read-only root filesystem
- No privileged escalation
- Network policies (optional)

### Networking
- LoadBalancer service
- Ingress with TLS
- Internal service discovery

## Troubleshooting

### Check Pod Status
```bash
kubectl describe pod -n paaim <pod-name>
```

### View Logs
```bash
kubectl logs -n paaim <pod-name>
kubectl logs -n paaim <pod-name> --previous  # Crashed pod logs
```

### Database Issues
```bash
# Connect to PostgreSQL
kubectl exec -it paaim-postgresql-0 -n paaim -- psql -U paaim
```

### Redis Issues
```bash
# Connect to Redis
kubectl exec -it paaim-redis-master-0 -n paaim -- redis-cli
```

## Scaling

### Manual Scaling
```bash
kubectl scale deployment paaim-api -n paaim --replicas=10
```

### Autoscaling
Horizontal Pod Autoscaler automatically scales based on CPU/memory metrics.

Monitor with:
```bash
kubectl get hpa -n paaim --watch
```

## Updates & Rollbacks

### Deploy New Version
```bash
helm upgrade paaim ./helm-chart \
  --set image.tag=0.2.0 \
  --namespace paaim
```

### Rollback
```bash
helm rollback paaim 1  # Rollback to previous release
```

## Cleanup

```bash
# Delete deployment
helm uninstall paaim -n paaim

# Delete namespace
kubectl delete namespace paaim
```

## Advanced Configuration

### Enable Network Policies
```yaml
networkPolicy:
  enabled: true
```

### Enable Pod Security Standards
```yaml
podSecurityPolicy: "restricted"
```

### Configure RBAC
```bash
kubectl apply -f rbac.yaml
```

## Production Checklist

- [ ] Secrets configured securely
- [ ] Persistent volumes configured
- [ ] HPA configured and tested
- [ ] Network policies enabled
- [ ] Monitoring/alerts configured
- [ ] Backup strategy in place
- [ ] Disaster recovery plan
- [ ] Load testing completed
- [ ] Security scanning passed
- [ ] Documentation updated
