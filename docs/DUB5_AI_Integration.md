# DUB5 AI Integration Guide

This document provides instructions on how to integrate the DUB5 AI backend into your applications and how to leverage its "coder" personality for web development tasks.

## Deployed URL

The DUB5 AI backend is deployed at: `chatbot-beta-weld.vercel.app`

All API endpoints will be prefixed with this URL. For example, to access the `/api/chatbot` endpoint, you would use `https://chatbot-beta-weld.vercel.app/api/chatbot`.

## Integrating DUB5 AI

The primary way to interact with the DUB5 AI is through its `/api/chatbot` endpoint. This endpoint accepts POST requests with a JSON payload containing the user's input, conversation history, desired personality, and other optional parameters.

### API Endpoint

-   **URL:** `https://chatbot-beta-weld.vercel.app/api/chatbot`
-   **Method:** `POST`
-   **Content-Type:** `application/json`

### Request Body

The request body should be a JSON object with the following structure:

```json
{
    "input": "Your message to the AI.",
    "history": [
        {"role": "user", "content": "Previous user message"},
        {"role": "assistant", "content": "Previous AI response"}
    ],
    "personality": "general", // or "coder", "creative", etc.
    "model": "auto", // Optional: specify a model, e.g., "gpt-4", "gemini", "auto"
    "web_search": false, // Optional: enable/disable web search
    "custom_system_prompt": null, // Optional: override the system prompt
    "force_roulette": false, // Optional: force model roulette
    "files": [], // Optional: list of file objects for context
    "image": null, // Optional: Base64 encoded image for analysis
    "session_id": "default", // Optional: session identifier
    "library_ids": [] // Optional: list of library IDs for RAG
}
```

-   `input` (string, required): The current message from the user.
-   `history` (array of objects, required): An array of past messages in the conversation. Each object should have a `role` (either "user" or "assistant") and `content` (the message text).
-   `personality` (string, required): The desired personality for the AI. Use `"coder"` for the AI web app builder.
-   `model` (string, optional): Specifies the AI model to use. Default is `"auto"`.
-   `web_search` (boolean, optional): If `true`, the AI may perform a web search to answer the query. Default is `false`.
-   `custom_system_prompt` (string, optional): A custom system prompt to override the default.
-   `force_roulette` (boolean, optional): If `true`, forces the AI to randomly select a model. Default is `false`.
-   `files` (array of objects, optional): A list of file objects, each with `name` and `content` (Base64 encoded or raw text).
-   `image` (string, optional): A Base64 encoded image for the AI to analyze.
-   `session_id` (string, optional): A unique identifier for the conversation session. Default is `"default"`.
-   `library_ids` (array of strings, optional): A list of IDs for documents stored in the knowledge library to be used for Retrieval Augmented Generation (RAG).

### Response Format (Streaming)

The API streams responses using Server-Sent Events (SSE). Each event will be a JSON object.

```
data: {"type": "metadata", "model": "openai", "personality": "coder"}

data: {"content": "Hello"}

data: {"content": " World!"}

data: [DONE]
```

-   `type: "metadata"`: Provides information about the model and personality used.
-   `content`: Contains chunks of the AI's response. These should be concatenated to form the full response.
-   `[DONE]`: Indicates the end of the stream.

### Example Client-Side (JavaScript Fetch API)

```javascript
async function sendMessageToDUB5(message, conversationHistory, personality = "general") {
    const url = "https://chatbot-beta-weld.vercel.app/api/chatbot";
    const payload = {
        input: message,
        history: conversationHistory,
        personality: personality
    };

    try {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`HTTP error! status: ${response.status}, message: ${errorText}`);
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let fullResponse = "";

        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            // Process each chunk, looking for SSE 'data:' lines
            chunk.split('\n').forEach(line => {
                if (line.startsWith('data: ')) {
                    const jsonStr = line.substring(6).trim();
                    if (jsonStr === '[DONE]') {
                        console.log("Stream finished.");
                        return;
                    }
                    try {
                        const eventData = JSON.parse(jsonStr);
                        if (eventData.type === "metadata") {
                            console.log("Metadata:", eventData);
                        } else if (eventData.content) {
                            fullResponse += eventData.content;
                            // You can update your UI here with partial response
                            console.log(eventData.content);
                        } else if (eventData.error) {
                            console.error("Error from chatbot:", eventData.error);
                        }
                    } catch (e) {
                        console.error("Failed to parse JSON from SSE chunk:", jsonStr, e);
                    }
                }
            });
        }
        return fullResponse;

    } catch (error) {
        console.error("Error sending message to DUB5 AI:", error);
        return null;
    }
}

// Example usage:
// let history = [];
// sendMessageToDUB5("Hello DUB5, how are you?", history, "general")
//     .then(response => {
//         if (response) {
//             history.push({"role": "user", "content": "Hello DUB5, how are you?"});
//             history.push({"role": "assistant", "content": response});
//             console.log("Full AI Response:", response);
//         }
//     });
```

## Adding Coder Personality

The "coder" personality is specifically designed for AI web app building. When you set `personality: "coder"` in your request payload, DUB5 AI will adhere to a set of rules optimized for code generation, including:

-   **BEGIN_FILE/END_FILE Format:** The AI will use `BEGIN_FILE <filename>` and `END_FILE` markers to delineate code blocks for different files. This allows for easy parsing and reconstruction of multiple files from a single response.
-   **Continuation:** If a response is truncated, you can send a follow-up message like "Continue EXACTLY where you left off" to prompt the AI to resume its code generation from the last point.
-   **Standalone HTML/CSS/JS:** By default, the coder personality is configured to generate standalone HTML, CSS, and JavaScript files, linked appropriately. It avoids frameworks like React/Next.js unless explicitly requested.

### Example Request for Coder Personality

```json
{
    "input": "Create a simple HTML page with a blue background and a 'Hello DUB5' heading. Also include a linked CSS file to style the heading red and a linked JS file to log 'Page loaded' to the console.",
    "history": [],
    "personality": "coder"
}
```

### Expected Coder Response Format (example)

```
data: {"content": "BEGIN_FILE index.html\n<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n    <meta charset=\"UTF-8\">\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n    <title>Hello DUB5</title>\n    <link rel=\"stylesheet\" href=\"style.css\">\n</head>\n<body>\n    <h1 id=\"main-heading\">Hello DUB5</h1>\n    <script src=\"script.js\"></script>\n</body>\n</html>\nEND_FILE\nBEGIN_FILE style.css\nbody {\n    background-color: blue;\n}\n#main-heading {\n    color: red;\n}\nEND_FILE\nBEGIN_FILE script.js\nconsole.log('Page loaded');\nEND_FILE"}
```

You would then parse this streamed response, extract the content between `BEGIN_FILE` and `END_FILE` markers, and save them as `index.html`, `style.css`, and `script.js` respectively.

## Error Handling

The API will return appropriate HTTP status codes for errors. In case of an AI-related error, the streamed response might include an `error` field in an event data. Always check `response.ok` in your client-side code and handle potential `HTTPStatusError` or `RequestError` from your HTTP client.

If you encounter a "Cloudflare Tunnel error" (Error 1033) or similar network issues, this indicates a problem with the external AI service provider (Pollinations AI). Please try again after a few minutes.
