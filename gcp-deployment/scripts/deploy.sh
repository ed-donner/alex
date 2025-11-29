#!/bin/bash
# =============================================================================
# GCP Deployment Script for Alex Multi-Agent SaaS
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${PROJECT_ID:-}"
REGION="${REGION:-us-central1}"
ENVIRONMENT="${ENVIRONMENT:-dev}"

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    if ! command -v gcloud &> /dev/null; then
        print_error "gcloud CLI is not installed"
        exit 1
    fi
    
    if ! command -v terraform &> /dev/null; then
        print_error "Terraform is not installed"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed"
        exit 1
    fi
    
    if [ -z "$PROJECT_ID" ]; then
        print_error "PROJECT_ID environment variable is not set"
        exit 1
    fi
    
    print_status "All prerequisites met!"
}

# Set up GCP project
setup_project() {
    print_status "Setting up GCP project..."
    
    gcloud config set project $PROJECT_ID
    gcloud config set compute/region $REGION
    
    # Enable APIs
    print_status "Enabling required APIs..."
    gcloud services enable \
        compute.googleapis.com \
        run.googleapis.com \
        cloudfunctions.googleapis.com \
        sqladmin.googleapis.com \
        aiplatform.googleapis.com \
        artifactregistry.googleapis.com \
        secretmanager.googleapis.com \
        cloudresourcemanager.googleapis.com \
        iam.googleapis.com \
        storage.googleapis.com \
        servicenetworking.googleapis.com \
        cloudbuild.googleapis.com
}

# Deploy phase
deploy_phase() {
    local phase=$1
    print_status "Deploying phase: $phase"
    
    cd "terraform/$phase"
    
    if [ ! -f "terraform.tfvars" ]; then
        print_warning "terraform.tfvars not found, using defaults"
        cp terraform.tfvars.example terraform.tfvars 2>/dev/null || true
    fi
    
    terraform init
    terraform plan -out=tfplan
    terraform apply tfplan
    
    cd ../..
}

# Build and push container images
build_images() {
    print_status "Building and pushing container images..."
    
    # Configure Docker for Artifact Registry
    gcloud auth configure-docker ${REGION}-docker.pkg.dev
    
    REPO="${REGION}-docker.pkg.dev/${PROJECT_ID}/alex-containers"
    
    # Build each agent
    for agent in researcher planner executor orchestrator; do
        if [ -d "backend/agents/$agent" ]; then
            print_status "Building $agent agent..."
            docker build -t ${REPO}/${agent}:latest -f backend/agents/$agent/Dockerfile backend/agents/$agent
            docker push ${REPO}/${agent}:latest
        fi
    done
    
    # Build frontend
    if [ -d "frontend" ]; then
        print_status "Building frontend..."
        docker build -t ${REPO}/frontend:latest frontend
        docker push ${REPO}/frontend:latest
    fi
}

# Full deployment
full_deploy() {
    check_prerequisites
    setup_project
    
    print_status "Starting full deployment..."
    
    # Phase 1: Permissions
    deploy_phase "1_permissions"
    
    # Phase 2: Vertex AI
    deploy_phase "2_vertex_ai"
    
    # Phase 5: Database (skipping 3 and 4 as they depend on actual code)
    deploy_phase "5_database"
    
    # Build images before deploying agents
    build_images
    
    # Phase 6: Agents
    deploy_phase "6_agents"
    
    # Phase 7: Frontend
    deploy_phase "7_frontend"
    
    print_status "Deployment complete!"
    print_status "Frontend URL: $(terraform -chdir=terraform/7_frontend output -raw frontend_url)"
    print_status "Backend API URL: $(terraform -chdir=terraform/6_agents output -raw orchestrator_url)"
}

# Destroy all resources
destroy_all() {
    print_warning "This will destroy all resources. Continue? (y/N)"
    read -r confirm
    
    if [ "$confirm" != "y" ]; then
        print_status "Aborted"
        exit 0
    fi
    
    for phase in 7_frontend 6_agents 5_database 2_vertex_ai 1_permissions; do
        print_status "Destroying $phase..."
        cd "terraform/$phase"
        terraform destroy -auto-approve || true
        cd ../..
    done
    
    print_status "All resources destroyed"
}

# Main
case "${1:-}" in
    "full")
        full_deploy
        ;;
    "phase")
        if [ -z "${2:-}" ]; then
            print_error "Please specify a phase (e.g., 1_permissions)"
            exit 1
        fi
        deploy_phase "$2"
        ;;
    "build")
        build_images
        ;;
    "destroy")
        destroy_all
        ;;
    *)
        echo "Usage: $0 {full|phase <name>|build|destroy}"
        echo ""
        echo "Commands:"
        echo "  full          - Run full deployment"
        echo "  phase <name>  - Deploy specific phase (e.g., 1_permissions)"
        echo "  build         - Build and push container images"
        echo "  destroy       - Destroy all resources"
        exit 1
        ;;
esac
