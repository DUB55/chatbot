# VERCEL DEPLOYMENT TROUBLESHOOTING GUIDE

## Problem: Local works, Vercel gives 500 error

## Step 1: Check GitHub-Vercel Connection
1. Go to Vercel dashboard
2. Check if your project is connected to correct GitHub repo
3. Look for any deployment errors in Vercel logs

## Step 2: Clear Vercel Cache
1. In Vercel dashboard → Project Settings → Git
2. Disconnect GitHub repo
3. Re-connect GitHub repo
4. This clears Vercel's build cache

## Step 3: Manual Deployment (If auto-deploy fails)
1. Install Vercel CLI: `npm i -g vercel`
2. Run: `vercel --prod`
3. This bypasses GitHub auto-deploy

## Step 4: Check Vercel Function Logs
1. Vercel dashboard → Functions tab
2. Look for specific error messages
3. Check if Python dependencies are installing correctly

## Step 5: Environment Variables
1. Vercel dashboard → Settings → Environment Variables
2. Ensure PYTHON_VERSION is set to "3.9"
3. Add any missing environment variables

## Most Likely Issues:
- **Build cache**: Vercel using old cached build
- **Dependency installation**: Python packages failing to install
- **Function timeout**: 60s limit being exceeded
- **Environment variables**: Missing required vars

## Quick Fix Commands:
```bash
# Force new deployment
vercel --prod --force

# Clear and redeploy
vercel rm your-app-name
vercel --prod
```
