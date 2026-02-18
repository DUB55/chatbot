import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handler(request):
    """Simple test handler for Vercel"""
    try:
        logger.info("Handler called successfully")
        
        # Return simple response
        response = {
            "status": "success",
            "message": "Vercel Python function is working",
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers)
        }
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps(response)
        }
        
    except Exception as e:
        logger.error(f"Error in handler: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*"
            },
            "body": json.dumps({
                "status": "error", 
                "message": str(e)
            })
        }
