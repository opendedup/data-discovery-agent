#!/bin/bash
# =============================================================================
# Run MCP Server
# =============================================================================
# Script to start the MCP service locally for testing
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Data Discovery Agent MCP Service${NC}"
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found${NC}"
    echo "Copying .env.example to .env..."
    cp .env.example .env
    echo -e "${RED}Please edit .env with your actual values before proceeding${NC}"
    exit 1
fi

# Load environment variables
echo "Loading environment from .env..."
set -a
source .env
set +a

# Validate required environment variables
REQUIRED_VARS=(
    "GCP_PROJECT_ID"
    "GCS_REPORTS_BUCKET"
    "VERTEX_DATASTORE_ID"
)

MISSING_VARS=()
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo -e "${RED}Error: Missing required environment variables:${NC}"
    for var in "${MISSING_VARS[@]}"; do
        echo "  - $var"
    done
    exit 1
fi

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}Warning: Not running in a virtual environment${NC}"
    echo "It's recommended to activate a virtual environment first:"
    echo "  python -m venv venv"
    echo "  source venv/bin/activate  # On Linux/Mac"
    echo "  venv\\Scripts\\activate   # On Windows"
    echo ""
fi

# Check if dependencies are installed
echo "Checking dependencies..."
python -c "import mcp" 2>/dev/null || {
    echo -e "${RED}Error: MCP library not installed${NC}"
    echo "Install dependencies with:"
    echo "  pip install -e ."
    echo "  or"
    echo "  poetry install"
    exit 1
}

# Display configuration
echo ""
echo -e "${GREEN}Configuration:${NC}"
echo "  Project ID:      $GCP_PROJECT_ID"
echo "  Reports Bucket:  $GCS_REPORTS_BUCKET"
echo "  Datastore ID:    $VERTEX_DATASTORE_ID"
echo "  Server Name:     ${MCP_SERVER_NAME:-data-discovery-agent}"
echo "  Server Version:  ${MCP_SERVER_VERSION:-1.0.0}"
echo "  Log Level:       ${LOG_LEVEL:-INFO}"
echo ""

# Start the server
echo -e "${GREEN}Starting MCP server...${NC}"
echo "Press Ctrl+C to stop"
echo ""

# Run the server
cd "$(dirname "$0")/.." || exit 1
python -m data_discovery_agent.mcp.server

# Cleanup on exit
echo ""
echo -e "${GREEN}MCP server stopped${NC}"

