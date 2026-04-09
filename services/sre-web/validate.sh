#!/usr/bin/env bash
# Pre-build validation for sre-web
# Run this before docker compose up --build to catch errors early.
set -e

cd "$(dirname "$0")"

echo "=== sre-web pre-build validation ==="

if [ ! -d "node_modules" ]; then
  echo "[1/2] Installing dependencies..."
  npm install --ignore-scripts
else
  echo "[1/2] node_modules found, skipping install"
fi

echo "[2/2] Running TypeScript type check..."
npx tsc --noEmit

echo ""
echo "All checks passed. Safe to run: docker compose up --build"
