#!/bin/bash
# =============================================================================
# Environment Validation Script
# Validates that all required environment variables are set before deployment
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Environment Validation${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Load .env file if it exists
if [[ -f .env ]]; then
    echo -e "${GREEN}✅ Loading .env file...${NC}"
    set -a
    source .env
    set +a
else
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env  # Edit with your API keys"
    exit 1
fi

# Define required variables
REQUIRED_VARS=(
    "DATABASE_URL"
    "REDIS_URL"
    "BYBIT_API_KEY"
    "BYBIT_API_SECRET"
    "TELEGRAM_BOT_TOKEN"
    "TELEGRAM_CHAT_ID"
)

# Define variables that should not use default values
NO_DEFAULT_VARS=(
    "DB_PASSWORD"
    "GRAFANA_PASSWORD"
)

MISSING=()
WEAK=()

echo -e "${YELLOW}Checking required environment variables...${NC}"
echo ""

# Check for missing variables
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]] || [[ "${!var}" == *"your_"* ]] || [[ "${!var}" == *"CHANGE_THIS"* ]]; then
        MISSING+=("$var")
    fi
done

# Check for weak passwords
for var in "${NO_DEFAULT_VARS[@]}"; do
    if [[ -n "${!var}" ]]; then
        # Check if password is too short or uses default
        if [[ ${#var} -lt 8 ]] || [[ "${!var}" == "CHANGE_THIS_TO_SECURE_PASSWORD" ]] || [[ "${!var}" == "admin123" ]]; then
            WEAK+=("$var")
        fi
    fi
done

# Report results
if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo -e "${RED}❌ Missing or unconfigured environment variables:${NC}"
    printf '  - %s\n' "${MISSING[@]}"
    echo ""
    echo "Please edit .env and set these values."
    echo "See .env.example for documentation."
    EXIT_CODE=1
else
    echo -e "${GREEN}✅ All required variables are configured${NC}"
    EXIT_CODE=0
fi

echo ""

if [[ ${#WEAK[@]} -gt 0 ]]; then
    echo -e "${RED}❌ Weak or default passwords detected:${NC}"
    printf '  - %s\n' "${WEAK[@]}"
    echo ""
    echo "SECURITY WARNING: Please set strong, unique passwords!"
    echo "Use a password manager to generate secure passwords."
    EXIT_CODE=1
else
    echo -e "${GREEN}✅ Password strength check passed${NC}"
fi

echo ""

# Check Python version
if command -v python3.11 &> /dev/null || command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
    echo -e "${GREEN}✅ Python $PYTHON_VERSION detected${NC}"
else
    echo -e "${RED}❌ Python 3.11+ not found!${NC}"
    echo "Please install Python 3.11 or higher."
    EXIT_CODE=1
fi

# Check if virtual environment exists
if [[ -d ".venv" ]]; then
    echo -e "${GREEN}✅ Virtual environment found${NC}"
else
    echo -e "${YELLOW}⚠️  Virtual environment not found${NC}"
    echo "Run: python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt"
fi

# Check if Docker is available (optional)
if command -v docker &> /dev/null; then
    echo -e "${GREEN}✅ Docker detected${NC}"
else
    echo -e "${YELLOW}⚠️  Docker not found (optional for containerized deployment)${NC}"
fi

echo ""

if [[ $EXIT_CODE -eq 0 ]]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}✅ Environment validation PASSED${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "You're ready to deploy! 🚀"
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}❌ Environment validation FAILED${NC}"
    echo -e "${RED}========================================${NC}"
    echo ""
    echo "Please fix the issues above before deploying."
fi

exit $EXIT_CODE
