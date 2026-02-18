@echo off
echo 🚀 DEPLOYING TO VERCEL MANUALLY...

REM Check if Vercel CLI is installed
vercel --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 Installing Vercel CLI...
    npm install -g vercel
)

REM Deploy with force flag to bypass cache
echo 🔄 Force deploying to bypass cache...
vercel --prod --force

echo ✅ Deployment complete!
echo 🌐 Check your Vercel dashboard for deployment status
echo 🔍 Test the live site at your Vercel URL
