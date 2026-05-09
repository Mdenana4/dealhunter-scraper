#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# DealHunter Egypt — ONE-COMMAND Deploy Script
# Run: chmod +x deploy_all.sh && ./deploy_all.sh
# ═══════════════════════════════════════════════════════════════════════════════

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  DealHunter Egypt — Full Deployment${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# ─── Check prerequisites ───
echo -e "${YELLOW}▶ Checking prerequisites...${NC}"
command -v git >/dev/null 2>&1 || { echo -e "${RED}✗ git not installed${NC}"; exit 1; }
echo -e "${GREEN}✓ git${NC}"

# ─── Step 1: GitHub Push ───
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  STEP 1/3: Push Flutter App to GitHub${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$(dirname "$0")/../flutter"

if ! git remote get-url origin >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ No remote configured${NC}"
    read -p "Enter your GitHub repo URL (e.g., https://github.com/YOURNAME/dealhunter.git): " REPO_URL
    git remote add origin "$REPO_URL"
fi

echo -e "${YELLOW}▶ Pushing to GitHub...${NC}"
git branch -M main 2>/dev/null || true
git push -u origin main --force
echo -e "${GREEN}✅ Flutter app pushed to GitHub${NC}"

# ─── Step 2: Render Deploy ───
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  STEP 2/3: Deploy API to Render${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$(dirname "$0")/../api"

if command -v render >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ Deploying to Render...${NC}"
    render deploy
    echo -e "${GREEN}✅ API deployed to Render${NC}"
else
    echo -e "${YELLOW}⚠ Render CLI not installed${NC}"
    echo "   Install: npm install -g @render/cli"
    echo "   Or deploy manually: https://dashboard.render.com"
    echo "   → New Web Service → Connect your GitHub repo"
fi

# ─── Step 3: Railway Deploy ───
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  STEP 3/3: Deploy Scraper to Railway${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

cd "$(dirname "$0")/../scraper"

if command -v railway >/dev/null 2>&1; then
    echo -e "${YELLOW}▶ Deploying to Railway...${NC}"
    railway up
    echo -e "${GREEN}✅ Scraper deployed to Railway${NC}"
else
    echo -e "${YELLOW}⚠ Railway CLI not installed${NC}"
    echo "   Install: npm install -g @railway/cli"
    echo "   Or deploy manually: https://railway.app"
fi

# ─── Done ───
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✅ DEPLOYMENT COMPLETE${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${BLUE}Your services:${NC}"
echo "  📱 Flutter App  → GitHub → CodeMagic builds APK/IPA"
echo "  🌐 API          → Render → https://dealhunter-api.onrender.com"
echo "  🔧 Scraper      → Railway → Runs 24/7"
echo ""
echo -e "${YELLOW}Next: Connect CodeMagic to your GitHub repo:${NC}"
echo "  1. Go to https://codemagic.io"
echo "  2. Sign in with GitHub"
echo "  3. Add 'dealhunter' application"
echo "  4. Build → Download APK"
echo ""
