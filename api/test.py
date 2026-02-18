def handler(request):
    """
    Minimal Vercel serverless function to test basic execution
    """
    try:
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": '{"message": "Serverless function works!", "method": "' + request.get("method", "unknown") + '"}'
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": '{"error": "' + str(e) + '"}'
        }
