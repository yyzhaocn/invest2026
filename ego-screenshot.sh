#!/bin/bash
# Usage: ./ego-screenshot.sh <URL>

URL="${1:-https://example.com}"

ego-browser nodejs <<'EOF'
const url = "${URL}"

const task = await useOrCreateTaskSpace('screenshot-' + (url.includes('://') ? new URL(url).hostname.replace(/\./g,'-') : 'unknown'))

await openOrReuseTab(url, { wait: true, timeout: 30 })

const path = await captureScreenshot('/tmp/1.png')

cliLog(`✅ Screenshot of ${url} saved to: ${path}`)
EOF
