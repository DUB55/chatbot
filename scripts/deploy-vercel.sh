#!/bin/bash

echo "🚀 DEPLOYING TO VERCEL MANUALLY..."

# Check if Vercel CLI is installed
if ! command -v vercel &> /dev/null
then
    echo "📦 Installing Vercel CLI..."
    npm install -g vercel
fi

# Deploy with force flag to bypass cache
echo "🔄 Force deploying to bypass cache..."
vercel --prod --force

echo "✅ Deployment complete!"
echo "🌐 Check your Vercel dashboard for deployment status"
echo "🔍 Test the live site at your Vercel URL"
