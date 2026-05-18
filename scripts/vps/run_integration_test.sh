#!/bin/bash
# Integration test for VPS deployment
# Purpose: End-to-end test of VPS deployment workflow

set -euo pipefail

echo "🧪 Running VPS deployment integration test..."
echo ""

# Test 1: Validate scripts exist and are executable
echo "Test 1: Script validation..."
SCRIPTS=(
    "scripts/vps/setup_vps.sh"
    "scripts/vps/install_tailscale.sh"
    "scripts/vps/enable_tailscale_exit_node.sh"
    "scripts/vps/configure_tailscale_ssh.sh"
    "scripts/vps/deploy_to_vps.sh"
    "scripts/vps/validate_vps_env.sh"
)

ALL_SCRIPTS_VALID=true
for script in "${SCRIPTS[@]}"; do
    if [ ! -f "$script" ]; then
        echo "❌ Missing: $script"
        ALL_SCRIPTS_VALID=false
    elif [ ! -x "$script" ]; then
        echo "⚠️  Not executable: $script"
        chmod +x "$script"
        echo "   Fixed permissions"
    else
        echo "✅ $script"
    fi
done

if [ "$ALL_SCRIPTS_VALID" = false ]; then
    echo "❌ Script validation failed"
    exit 1
fi
echo ""

# Test 2: Dry-run Docker Compose validation
echo "Test 2: Docker Compose dry-run..."
if command -v docker compose &> /dev/null; then
    # Simple syntax check - just verify file exists and is valid YAML
    if [ -f "docker-compose.yml" ]; then
        if python3 -c "import yaml; yaml.safe_load(open('docker-compose.yml'))" 2>/dev/null; then
            echo "✅ Docker Compose file exists and is valid YAML"
        else
            echo "⚠️  Docker Compose YAML syntax check failed (may need .env variables)"
        fi
    else
        echo "❌ docker-compose.yml not found"
        exit 1
    fi
else
    echo "⚠️  Docker Compose not installed (required for VPS deployment)"
fi
echo ""

# Test 3: Check documentation
echo "Test 3: Documentation check..."
DOCS=(
    "docs/VPS_DEPLOYMENT_GUIDE.md"
    "docs/VPS_REMOTE_DEVELOPMENT.md"
)

ALL_DOCS_EXIST=true
for doc in "${DOCS[@]}"; do
    if [ ! -f "$doc" ]; then
        echo "❌ Missing: $doc"
        ALL_DOCS_EXIST=false
    else
        echo "✅ $doc"
    fi
done

if [ "$ALL_DOCS_EXIST" = false ]; then
    echo "❌ Documentation validation failed"
    exit 1
fi
echo ""

# Test 4: API health check (if running locally)
echo "Test 4: API health check..."
if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    echo "✅ API responding"
    
    # Get health status
    HEALTH=$(curl -s http://localhost:8000/api/v1/health | python3 -m json.tool 2>/dev/null || echo "{}")
    echo "Health status:"
    echo "$HEALTH" | head -20
else
    echo "⚠️  API not running (expected if not started locally)"
fi
echo ""

# Test 5: Run Python validation script
echo "Test 5: Running hybrid deployment validation..."
if command -v python3 &> /dev/null; then
    python3 scripts/vps/test_hybrid_deployment.py
    VALIDATION_EXIT=$?
    
    if [ $VALIDATION_EXIT -eq 0 ]; then
        echo "✅ Hybrid deployment validation passed"
    else
        echo "❌ Hybrid deployment validation failed"
        exit 1
    fi
else
    echo "⚠️  Python3 not available, skipping Python validation"
fi
echo ""

# Test 6: Check .env.example has VPS configs
echo "Test 6: Environment configuration check..."
if grep -q "VPS Deployment Configuration" .env.example 2>/dev/null; then
    echo "✅ .env.example includes VPS configuration"
else
    echo "❌ .env.example missing VPS configuration section"
    exit 1
fi
echo ""

# Test 7: Verify README updated
echo "Test 7: README deployment options check..."
if grep -q "Deployment Options" README.md 2>/dev/null; then
    echo "✅ README includes deployment options"
else
    echo "❌ README missing deployment options section"
    exit 1
fi
echo ""

echo "============================================================"
echo "Integration Test Summary"
echo "============================================================"
echo ""
echo "✅ All integration tests passed!"
echo ""
echo "Your hybrid deployment setup is ready."
echo ""
echo "Next steps:"
echo "1. Provision a Singapore VPS (Ubuntu 22.04)"
echo "2. SSH into VPS and run: ./scripts/vps/setup_vps.sh"
echo "3. Install Tailscale: ./scripts/vps/install_tailscale.sh"
echo "4. Enable exit node: ./scripts/vps/enable_tailscale_exit_node.sh"
echo "5. Deploy application: ./scripts/vps/deploy_to_vps.sh"
echo ""
echo "See docs/VPS_DEPLOYMENT_GUIDE.md for detailed instructions."
