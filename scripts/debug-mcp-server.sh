#!/bin/bash
# ==============================================================================
# Debug MCP Server
# ==============================================================================
#
# This script helps debug the MCP server by running it in standalone mode
# with enhanced logging.
#
# Usage:
#   ./scripts/debug-mcp-server.sh
#
# For even more detailed debugging:
#   LOG_LEVEL=DEBUG ./scripts/debug-mcp-server.sh
#
# ==============================================================================

set -euo pipefail

echo "================================================================================"
echo "  MCP Server - Debug Mode"
echo "================================================================================"
echo ""
echo "This will start the MCP server in standalone mode."
echo "You can:"
echo "  • Attach a Python debugger (pdb, ipdb, etc.)"
echo "  • See detailed logs in real-time"
echo "  • Test the server independently"
echo ""
echo "To test with the client, run in another terminal:"
echo "  python examples/mcp_client_example.py"
echo ""
echo "================================================================================"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found"
    echo "Please create .env with required variables (see .env.example)"
    echo ""
fi

# Load environment variables from .env if it exists
if [ -f ".env" ]; then
    echo "Loading environment variables from .env..."
    set -a
    source .env
    set +a
    echo "✓ Environment loaded"
    echo ""
fi

# Set debug log level if not already set
export LOG_LEVEL="${LOG_LEVEL:-INFO}"

echo "Starting MCP server..."
echo "Log Level: $LOG_LEVEL"
echo "Project: ${GCP_PROJECT_ID:-not set}"
echo "Reports Bucket: ${GCS_REPORTS_BUCKET:-not set}"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""
echo "================================================================================"
echo ""

# Run the server using the example script in server-only mode
python examples/mcp_client_example.py --server-only

