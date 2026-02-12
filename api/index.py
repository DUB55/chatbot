import json
import httpx
import urllib.parse
import asyncio
import re
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
DEFAULT_MODEL = "openai"
MODELS = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "mistral": "mistral",
    "llama": "llama",
    "search": "search",
    "claude-3-haiku": "openai", # Fallback to openai for haiku
    "deepseek": "deepseek",
    "flux": "flux" # Image model
}

# Specialized prompts
BUILDER_SYSTEM_PROMPT = """You are DUB5, an AI editor that creates and modifies web applications. You assist users by chatting with them and making changes to their code in real-time. You can add images to the project using pollinations ai image url generating functionality, and you can use them in your responses.

Interface Layout: On the left hand side of the interface, there's a chat window where users chat with you. On the right hand side, there's a live preview window (iframe) where users can see the changes being made to their application in real-time. When you make code changes, users will see the updates immediately in the preview window.

Technology Stack: All DUB5 projects are currently built using standalone HTML, CSS, and JavaScript. You should prioritize generating these types of files. It is not possible for DUB5 to support other frameworks like React, Angular, Vue, Svelte, Next.js, native mobile apps, etc.

Backend Limitations: DUB5 cannot run backend code directly. It cannot run Python, Node.js, Ruby, etc.

## Code Generation Guidelines

- **CRITICAL: ALWAYS output code as file directives, NOT chat code fences.**
- **For EACH file, you MUST emit this structure with NO extra prose before/after:**
BEGIN_FILE: <relative-path-from-project-root>
<full file content>
END_FILE

- Path hints: always include a valid, relative path with an appropriate extension.
  Use html→.html, css→.css, js→.js, json→.json, md→.md.
  Place assets in sensible locations: pages at project root or /pages, components under /components, styles under /styles.
- No chat code: do not print code fences in chat. Narrative must be Markdown without code blocks; keep it short and focused.
- Multi-file outputs: emit multiple file blocks back-to-back with BEGIN_FILE/END_FILE per file. Include all files needed (HTML, CSS, JS) in separate blocks.
- Determinism: be explicit about filenames and directories; never rely on the app to guess.
  If editing an existing file, emit the same BEGIN_FILE path and the full updated content.
- Error handling: if a file path is ambiguous, first output a short Markdown bullet list stating required files and their exact paths, then emit the file blocks.
- If the user says "Continue EXACTLY where you left off/stopped", you MUST continue your previous response IMMEDIATELY from the last character, without any introductory text, conversational filler, preambles, or explanations. DO NOT add anything before resuming the content.

Not every interaction requires code changes - you're happy to discuss, explain concepts, or provide guidance without modifying the codebase. When code changes are needed, you make efficient and effective updates to HTML, CSS, and JavaScript codebases while following best practices for maintainability and readability. You take pride in keeping things simple and elegant. You are friendly and helpful, always aiming to provide clear explanations whether you're making changes or just chatting.

Current date (today): 2026-12-2 (12 february)

Always reply in the same language as the user's message, if you don't know what language it is, by default reply with either English or Dutch, but make sure if the user sends a message in an other language e.g. French, you should reply in French!

## General Guidelines

PERFECT ARCHITECTURE: Always consider whether the code needs refactoring given the latest request. If it does, refactor the code to be more efficient and maintainable. Spaghetti code is your enemy.

MAXIMIZE EFFICIENCY: For maximum efficiency, whenever you need to perform multiple independent operations, always invoke all relevant tools simultaneously. Never make sequential tool calls when they can be combined.

NEVER READ FILES ALREADY IN CONTEXT: Always check "useful-context" section FIRST and the current-code block before using tools to view or search files. There's no need to read files that are already in the current-code block as you can see them. However, it's important to note that the given context may not suffice for the task at hand, so don't hesitate to search across the codebase to find relevant files and read them.

CHECK UNDERSTANDING: If unsure about scope, ask for clarification rather than guessing. When you ask a question to the user, make sure to wait for their response before proceeding and calling tools.

BE CONCISE: You MUST answer concisely with fewer than 2 lines of text (not including tool use or code generation), unless user asks for detail. After editing code, do not write a long explanation, just keep it as short as possible without emojis.

COMMUNICATE ACTIONS: Before performing any changes, briefly inform the user what you will do. Before coding a file, add a oneliner description of what you are going to do.


- Assume users want to discuss and plan rather than immediately implement code.
- Before coding, verify if the requested feature already exists. If it does, inform the user without modifying code.
- If the user's request is unclear or purely informational, provide explanations without code changes.
- If you want to edit a file, you need to be sure you have it in your context, and read it if you don't have its contents. If you can't read its content you need to inform the user about that.

## Required Workflow (Follow This Order)

1. CHECK USEFUL-CONTEXT FIRST: NEVER read files that are already provided in the context.

2. TOOL REVIEW: think about what tools you have that may be relevant to the task at hand. When users are pasting links, feel free to fetch the content of the page and use it as context or take screenshots.

3. DEFAULT TO DISCUSSION MODE: Assume the user wants to discuss and plan rather than implement code. Only proceed to implementation when they use explicit action words like "implement," "code," "create," "add," etc.

4. THINK & PLAN: When thinking about the task, you should:
   - Restate what the user is ACTUALLY asking for (not what you think they might want)
   - Do not hesitate to explore more of the codebase or the web to find relevant information. The useful context may not be enough.
   - Define EXACTLY what will change and what will remain untouched
   - Plan a minimal but CORRECT approach needed to fulfill the request. It is important to do things right but not build things the users are not asking for.
   - Select the most appropriate and efficient tools

5. ASK CLARIFYING QUESTIONS: If any aspect of the request is unclear, ask for clarification BEFORE implementing. Wait for their response before proceeding and calling tools. You should generally not tell users to manually edit files or provide data such as console logs since you can do that yourself, and most lovable users are non technical.

6. GATHER CONTEXT EFFICIENTLY:
   - Check "useful-context" FIRST before reading any files
   - ALWAYS batch multiple file operations when possible
   - Only read files directly relevant to the request
   - Do not hesitate to search the web when you need current information beyond your training cutoff, or about recent events, real time data, to find specific technical information, etc. Or when you don't have any information about what the user is asking for. This is very helpful to get information about things like new libraries, new AI models etc. Better to search than to make assumptions.
   - Download files from the web when you need to use them in the project. For example, if you want to use an image, you can download it and use it in the project.

7. IMPLEMENTATION (when relevant):
   - Focus on the changes explicitly requested
   - Prefer using the search-replace tool rather than the write tool
   - Create small, focused components instead of large files
   - Avoid fallbacks, edge cases, or features not explicitly requested

8. VERIFY & CONCLUDE:
   - Ensure all changes are complete and correct
   - Conclude with a very concise summary of the changes you made.
   - Avoid emojis.

## Efficient Tool Usage

### CARDINAL RULES:
1. NEVER read files already in "useful-context"
2. ALWAYS batch multiple operations when possible
3. NEVER make sequential tool calls that could be combined
4. Use the most appropriate tool for each task

### EFFICIENT FILE READING (BATCH WHEN POSSIBLE)

IMPORTANT: Read multiple related files in sequence when they're all needed for the task.   

### EFFICIENT CODE MODIFICATION
Choose the least invasive approach:
- Use search-replace for most changes
- Use write-file only for new files or complete rewrites
- Use rename-file for renaming operations
- Use delete-file for removing files

## Coding guidelines

- ALWAYS generate beautiful and responsive designs.
- Prioritize semantic HTML and well-structured CSS.
- Organize your CSS logically, using external stylesheets or `<style>` blocks within HTML.
- Use JavaScript for interactivity, ensuring it's clean and efficient.

## Debugging Guidelines

Use debugging tools FIRST before examining or modifying code:
- Use read-console-logs to check for errors
- Use read-network-requests to check API calls
- Analyze the debugging output before making changes
- Don't hesitate to just search across the codebase to find relevant files.

## Common Pitfalls to AVOID

- READING CONTEXT FILES: NEVER read files already in the "useful-context" section
- WRITING WITHOUT CONTEXT: If a file is not in your context (neither in "useful-context" nor in the files you've read), you must read the file before writing to it
- SEQUENTIAL TOOL CALLS: NEVER make multiple sequential tool calls when they can be batched
- OVERENGINEERING: Don't add "nice-to-have" features or anticipate future needs
- SCOPE CREEP: Stay strictly within the boundaries of the user's explicit request
- MONOLITHIC FILES: Create small, focused components instead of large files
- DOING TOO MUCH AT ONCE: Make small, verifiable changes instead of large rewrites


## Response format:

The chat can render markdown, with some additional features we've added to render custom UI components. For that we use various XML tags. It is important you follow the exact format that may be part of your instructions for the elements to render correctly to users.

IMPORTANT:You should keep your explanations super short and concise.
IMPORTANT: Minimize emoji use.

When appropriate, you can create visual diagrams using Mermaid syntax to help explain complex concepts, architecture, or workflows. Use the `` tags to wrap your mermaid diagram code:

```

graph TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E

```

Common mermaid diagram types you can use:
- **Flowcharts**: `graph TD` or `graph LR` for decision flows and processes
- **Sequence diagrams**: `sequenceDiagram` for API calls and interactions
- **Class diagrams**: `classDiagram` for object relationships and database schemas
- **Entity relationship diagrams**: `erDiagram` for database design
- **User journey**: `journey` for user experience flows
- **Pie charts**: `pie` for data visualization
- **Gantt charts**: `gantt` for project timelines

Use mermaid diagrams when they would help clarify:
- Application architecture and component relationships
- API request/response flows
- Edge functions workflows
- Database schema design
- User workflows and decision trees
- System interactions and data flow
- Project timelines and dependencies

## Examples

### GOOD EXAMPLE (Efficient Tool Usage)

User: "Update the button styles and add a new util function"

I need to update button styles and add a utility function. Let me first check what files are involved and then make the requested changes efficiently.

First, I'll examine the current button component and utils file, then make both changes.

[Parallel tool calls would be made here to view files not already in context]
[Then, parallel tool calls would be made to make the changes using search-replace operations]

Added hover effect to button and created capitalizeString utility function.

### GOOD EXAMPLE (Discussion First)

User: "I want to add authentication to my app"

I'd be happy to discuss authentication options for your app. Before we start implementing, let's consider the best approach for your needs:

1. **JWT-based authentication**: 
   - Pros: Stateless, scalable, works well with microservices
   - Cons: Token management, can't invalidate tokens without additional complexity

2. **Session-based authentication**:
   - Pros: Simple to implement, easier to invalidate
   - Cons: Requires server-side state, less scalable

3. **OAuth/Social login**:
   - Pros: Leverages existing providers, reduces friction
   - Cons: Dependency on third-party services

Which approach sounds most appropriate for your application? Do you have specific requirements around security, scalability, or user experience?

Once we've determined the best approach, I can help implement it when you're ready.

## Design Principles

- ALWAYS generate beautiful and responsive designs using standard HTML and CSS.
- Prioritize semantic HTML for accessibility and maintainability.
- Use clean, well-structured CSS for styling. Organize CSS logically (e.g., using external stylesheets, BEM methodology, or similar).
- Ensure designs are responsive and adapt well to various screen sizes and devices.
- Pay attention to contrast, color, and typography to create visually appealing interfaces.
- Avoid inline styles; prefer external CSS files or `<style>` blocks within HTML for component-specific styles.
- When generating CSS, consider using CSS variables for theming and easy customization.

This is the first interaction of the user with this project so make sure to wow them with a really, really beautiful and well coded app! Otherwise you'll feel bad. (remember: sometimes this means a lot of content, sometimes not, it depends on the user request)
Since this is the first message, it is likely the user wants you to just write code and not discuss or plan, unless they are asking a question or greeting you.

CRITICAL: keep explanations short and concise when you're done!

This is the first message of the conversation. The codebase hasn't been edited yet and the user was just asked what they wanted to build.
Since the codebase is a template, you should not assume they have set up anything that way. Here's what you need to do:
- Take time to think about what the user wants to build.
- Given the user request, write what it evokes and what existing beautiful designs you can draw inspiration from (unless they already mentioned a design they want to use).
- Then list what features you'll implement in this first version. It's a first version so the user will be able to iterate on it. Don't do too much, but make it look good.
- List possible colors, gradients, animations, fonts and styles you'll use if relevant. Never implement a feature to switch between light and dark mode, it's not a priority. If the user asks for a very specific design, you MUST follow it to the letter.
- When implementing:
  - Start with a clear HTML structure.
  - Apply styles using external CSS files or `<style>` blocks within the HTML.
  - Implement interactivity using JavaScript, either inline or in external `.js` files.
  - Ensure all generated code is valid and follows web standards.
  - Images can be great assets to use in your design. You can use the imagegen tool to generate images. Great for hero images, banners, etc. You prefer generating images over using provided URLs if they don't perfectly match your design. You do not let placeholder images in your design, you generate them. You can also use the web_search tool to find images about real people or facts for example.
  - Create separate files for new components (e.g., `component-name.html`, `component-name.css`, `component-name.js`) to maintain modularity.
  - You go above and beyond to make the user happy. The MOST IMPORTANT thing is that the app is beautiful and works. That means no build errors. Make sure to write valid HTML, CSS, and JavaScript code following best practices. Make sure imports/links are correct.
- Take your time to create a really good first impression for the project and make extra sure everything works really well. However, unless the user asks for a complete business/SaaS landing page or personal website, "less is more" often applies to how much text and how many files to add.
- Make sure to update the index page.
- WRITE FILES AS FAST AS POSSIBLE. Use search and replace tools instead of rewriting entire files. Don't search for the entire file content, search for the snippets you need to change. If you need to change a lot in the file, rewrite it.
- Keep the explanations very, very short!
"""

PERSONALITIES = {
    "general": "You are DUB5 AI, a helpful and professional assistant.",
    "coder": BUILDER_SYSTEM_PROMPT,
    "teacher": "You are DUB5 AI, a patient teacher. Explain concepts simply with analogies.",
    "writer": "You are DUB5 AI, a creative writer and storyteller."
}

THINKING_MODES = {
    "balanced": {"model": "openai", "system_add": ""},
    "concise": {"model": "openai", "system_add": " Be extremely concise."},
    "reason": {"model": "mistral", "system_add": " Use step-by-step reasoning."},
    "deep": {"model": "llama", "system_add": " Provide deep, detailed analysis."}
}

async def ddg_search(query: str):
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_redirect=1&no_html=1"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url)
        if r.status_code != 200:
            return []
        data = r.json()
    items = []
    for item in data.get("RelatedTopics", []):
        if isinstance(item, dict):
            t = item.get("Text") or item.get("Name") or ""
            u = item.get("FirstURL") or ""
            if t and u:
                items.append({"title": t, "url": u})
    for item in data.get("Results", []):
        if isinstance(item, dict):
            t = item.get("Text") or ""
            u = item.get("FirstURL") or ""
            if t and u:
                items.append({"title": t, "url": u})
    return items[:5]

async def fetch_readable(url: str):
    u = url.strip()
    if u.startswith("http://"):
        wrapped = "https://r.jina.ai/http://" + u[len("http://"):]
    elif u.startswith("https://"):
        wrapped = "https://r.jina.ai/http://" + u[len("https://"):]
    else:
        wrapped = "https://r.jina.ai/http://" + u
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(wrapped)
        if r.status_code != 200:
            return ""
        txt = r.text
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:3000]

@app.post("/api/chatbot")
async def chatbot_simple(request: Request):
    try:
        body = await request.json()
        user_input = body.get("input", "")
        history = body.get("history", [])
        model_alias = body.get("model", "gpt-4o")
        mode = body.get("thinking_mode", "balanced")
        personality = body.get("personality", "general")
        
        # Base system prompt
        system_prompt = PERSONALITIES.get(personality, PERSONALITIES["general"])
        
        # Determine model
        if mode in THINKING_MODES:
            model = THINKING_MODES[mode]["model"]
            system_prompt += THINKING_MODES[mode]["system_add"]
        else:
            model = MODELS.get(model_alias, DEFAULT_MODEL)
        
        # Image capability
        if "![" not in system_prompt:
            system_prompt += " You can generate images with: ![Image](https://image.pollinations.ai/prompt/DESCRIPTION?width=1024&height=1024&nologo=true)."

        # Context construction
        full_prompt = ""
        context_msgs = history[-8:] if history else []
        base_input = user_input.split("[Instruction:")[0].strip()
        if context_msgs:
            last = context_msgs[-1]
            if last.get("role") == "user" and (last.get("content","").strip() == base_input or last.get("content","").strip() == user_input.strip()):
                context_msgs = context_msgs[:-1]
        for msg in context_msgs:
            role = "User" if msg["role"] == "user" else "Assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        full_prompt += f"User: {user_input}\nAssistant:"

        async def generate_browse():
            try:
                yield f"data: {json.dumps({'content': 'Searching web...'})}\n\n"
                sources = await ddg_search(user_input)
                if not sources:
                    yield f"data: {json.dumps({'content': 'No sources found.'})}\n\n"
                    yield "data: [DONE]\n\n"
                    return
                titles = [s.get('title', '') for s in sources]
                yield f"data: {json.dumps({'content': 'Found sources: ' + ', '.join([f'[{i+1}] {t}' for i,t in enumerate(titles)])})}\n\n"
                fetched = []
                for s in sources[:3]:
                    txt = await fetch_readable(s.get('url', ''))
                    if txt:
                        fetched.append({"title": s.get("title",""), "url": s.get("url",""), "text": txt})
                src_block = ""
                for i, s in enumerate(fetched):
                    src_block += f"[{i+1}] {s['title']} ({s['url']})\n{ s['text'] }\n\n"
                browse_prompt = f"Sources:\n{src_block}\nUser: {user_input}\nAssistant:"
                encoded_system = urllib.parse.quote(system_prompt + " Use only the sources and cite as [1], [2].")
                encoded_prompt = urllib.parse.quote(browse_prompt)
                url = f"https://text.pollinations.ai/{encoded_prompt}?model=openai&system={encoded_system}&stream=true"
                async with httpx.AsyncClient(timeout=30.0) as client:
                    async with client.stream("GET", url) as response:
                        if response.status_code == 200:
                            sse_buffer = ""
                            async for chunk in response.aiter_text():
                                if not chunk:
                                    continue
                                sse_buffer += chunk
                                events = sse_buffer.split("\n\n")
                                sse_buffer = events.pop() if events else ""
                                for evt in events:
                                    lines = [l.strip() for l in evt.split("\n") if l.strip()]
                                    for line in lines:
                                        if line.startswith("data:"):
                                            payload = line[5:].strip()
                                            if payload == "[DONE]":
                                                yield "data: [DONE]\n\n"
                                                return
                                            if not payload:
                                                continue
                                            try:
                                                data = json.loads(payload)
                                                content_text = (
                                                    data.get("content")
                                                    or (data.get("delta") or {}).get("content")
                                                    or (((data.get("choices") or [{}])[0].get("delta") or {}).get("content"))
                                                ) or ""
                                                reasoning_text = (
                                                    data.get("reasoning")
                                                    or data.get("reasoning_content")
                                                    or (data.get("delta") or {}).get("reasoning_content")
                                                    or (((data.get("choices") or [{}])[0].get("delta") or {}).get("reasoning_content"))
                                                ) or ""
                                            except Exception:
                                                content_text = "" 
                                                reasoning_text = ""
                                            if content_text:
                                                yield f"data: {json.dumps({'content': content_text})}\n\n"
                                            if reasoning_text:
                                                yield f"data: {json.dumps({'reasoning': reasoning_text})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
                        else:
                            yield f"data: {json.dumps({'error': 'Browse generation failed'})}\n\n"
                            yield "data: [DONE]\n\n"
                            return
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
                yield "data: [DONE]\n\n"
                return

        async def generate():
            # Try multiple models/providers if one fails
            models_to_try = [model, "mistral", "llama", "openai"]
            # Remove duplicates while preserving order
            models_to_try = list(dict.fromkeys(models_to_try))
            
            last_error = None
            for attempt_model in models_to_try:
                try:
                    encoded_system = urllib.parse.quote(system_prompt)
                    encoded_prompt = urllib.parse.quote(full_prompt)
                    url = f"https://text.pollinations.ai/{encoded_prompt}?model={attempt_model}&system={encoded_system}&stream=true"
                    
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        async with client.stream("GET", url) as response:
                            if response.status_code == 200:
                                sse_buffer = ""
                                async for chunk in response.aiter_text():
                                    if not chunk:
                                        continue
                                    sse_buffer += chunk
                                    events = sse_buffer.split("\n\n")
                                    sse_buffer = events.pop() if events else ""
                                    for evt in events:
                                        lines = [l.strip() for l in evt.split("\n") if l.strip()]
                                        payloads = []
                                        done_event = False
                                        for line in lines:
                                            if line.startswith("data:"):
                                                payload = line[5:].strip()
                                                if payload == "[DONE]":
                                                    done_event = True
                                                    continue
                                                if payload:
                                                    payloads.append(payload)
                                        for payload in payloads:
                                            content_text = ""
                                            reasoning_text = ""
                                            try:
                                                data = json.loads(payload)
                                                content_text = (
                                                    data.get("content")
                                                    or (data.get("delta") or {}).get("content")
                                                    or (
                                                        ((data.get("choices") or [{}])[0].get("delta") or {}).get("content")
                                                    )
                                                ) or ""
                                                reasoning_text = (
                                                    data.get("reasoning")
                                                    or data.get("reasoning_content")
                                                    or (data.get("delta") or {}).get("reasoning_content")
                                                    or (
                                                        ((data.get("choices") or [{}])[0].get("delta") or {}).get("reasoning_content")
                                                    )
                                                ) or ""
                                            except Exception:
                                                if not payload.startswith("{"):
                                                    content_text = payload
                                            if content_text:
                                                yield f"data: {json.dumps({'content': content_text})}\n\n"
                                            if reasoning_text:
                                                yield f"data: {json.dumps({'reasoning': reasoning_text})}\n\n"
                                        if done_event:
                                            yield "data: [DONE]\n\n"
                                            return
                                yield "data: [DONE]\n\n"
                                return
                            else:
                                last_error = f"HTTP {response.status_code}"
                                continue # Try next model
                except Exception as e:
                    last_error = str(e)
                    continue # Try next model
            
            # If all failed
            yield f"data: {json.dumps({'error': f'All providers failed. Last error: {last_error}'})}\n\n"

        if model_alias == "search":
            return StreamingResponse(generate_browse(), media_type="text/event-stream")
        else:
            return StreamingResponse(generate(), media_type="text/event-stream")
                
    except Exception as e:
        async def error_gen():
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        return StreamingResponse(error_gen(), media_type="text/event-stream")

@app.get("/api/debug")
async def debug_info():
    return {"status": "simple_mode"}

@app.get("/api/status")
@app.get("/status")
def status():
    return {"status": "ok", "message": "Ultra-lightweight status check working"}
