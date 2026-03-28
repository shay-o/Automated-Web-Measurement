"""FastAPI web app providing a chat interface to Oakland's open data."""

import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Add project root to path so we can import oakland_mcp
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic
from oakland_mcp import tools

app = FastAPI(title="Oakland Open Data Chat")

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

TOOL_DEFINITIONS = [
    {
        "name": "search_datasets",
        "description": (
            "Search Oakland's open data portal for datasets matching keywords. "
            "Use when the user mentions a topic or data type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keywords to search for"},
                "category": {
                    "type": "string",
                    "description": "Optional category filter (e.g., 'Public Safety')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (1-50, default 10)",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "list_categories",
        "description": "List all dataset categories on Oakland's open data portal.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_dataset_info",
        "description": (
            "Get detailed metadata and column schema for a dataset. "
            "Call before query_dataset to learn column names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "Socrata dataset ID (e.g., 'ym6k-rx7a')",
                },
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "preview_dataset",
        "description": "Get a sample of actual data rows from a dataset with no filtering.",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Socrata dataset ID"},
                "limit": {
                    "type": "integer",
                    "description": "Sample rows (1-50, default 10)",
                    "default": 10,
                },
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "query_dataset",
        "description": (
            "Query a dataset with structured SoQL clauses. Call get_dataset_info "
            "first to know valid column names."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Socrata dataset ID"},
                "select": {
                    "type": "string",
                    "description": "Columns/aggregations (e.g., 'crimetype, count(*) as cnt')",
                },
                "where": {
                    "type": "string",
                    "description": "Filter (e.g., \"crimetype = 'ROBBERY'\")",
                },
                "order": {"type": "string", "description": "Sort (e.g., 'datetime DESC')"},
                "group": {"type": "string", "description": "Group by columns"},
                "having": {"type": "string", "description": "Filter on aggregates"},
                "limit": {"type": "integer", "description": "Max rows (1-5000)", "default": 500},
                "offset": {"type": "integer", "description": "Pagination offset", "default": 0},
            },
            "required": ["dataset_id"],
        },
    },
    {
        "name": "get_column_stats",
        "description": (
            "Get distinct values and frequency counts for a dataset column. "
            "Useful for understanding what values exist before querying."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Socrata dataset ID"},
                "column_name": {
                    "type": "string",
                    "description": "Exact column name to analyze",
                },
            },
            "required": ["dataset_id", "column_name"],
        },
    },
]

TOOL_FUNCTIONS = {
    "search_datasets": tools.search_datasets,
    "list_categories": tools.list_categories,
    "get_dataset_info": tools.get_dataset_info,
    "preview_dataset": tools.preview_dataset,
    "query_dataset": tools.query_dataset,
    "get_column_stats": tools.get_column_stats,
}

SYSTEM_PROMPT = """You are an Oakland Open Data assistant. You help users explore and analyze 
public government data from Oakland, California's open data portal (data.oaklandca.gov).

You have tools to search for datasets, view metadata, preview data, run queries, and get 
column statistics. Follow this workflow:

1. Search for relevant datasets using search_datasets
2. Get metadata with get_dataset_info to understand columns
3. Preview data or get column stats to understand values
4. Query with specific filters using query_dataset

Always explain what data you found and what it means. If a query returns no results, 
suggest alternative approaches. Be specific about data limitations (e.g., date ranges, 
missing fields).

Keep responses concise but informative. Format data clearly when presenting results."""


async def execute_tool(name: str, args: dict[str, Any]) -> str:
    """Execute a tool function by name with the given arguments."""
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return f"Unknown tool: {name}"
    try:
        return await func(**args)
    except Exception as e:
        return f"Error executing {name}: {e}"


@app.get("/", response_class=HTMLResponse)
async def index():
    return (STATIC_DIR / "index.html").read_text()


@app.post("/api/chat")
async def chat(request: Request):
    """Handle a chat message, executing tool calls as needed."""
    body = await request.json()
    user_message = body.get("message", "")
    conversation_history = body.get("history", [])

    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not configured. Set it in .env file."}

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    messages = conversation_history + [{"role": "user", "content": user_message}]

    all_tool_calls = []

    # Agentic loop: keep calling Claude until it produces a final text response
    max_iterations = 10
    for _ in range(max_iterations):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            # Extract tool calls and execute them
            assistant_content = response.content
            messages.append({"role": "assistant", "content": assistant_content})

            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    tool_name = block.name
                    tool_input = block.input
                    result = await execute_tool(tool_name, tool_input)

                    all_tool_calls.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "result": result[:500] + "..." if len(result) > 500 else result,
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })

            messages.append({"role": "user", "content": tool_results})
        else:
            # Final text response
            text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

            return {
                "response": text,
                "tool_calls": all_tool_calls,
                "messages": messages + [{"role": "assistant", "content": text}],
            }

    return {"error": "Max tool call iterations reached.", "tool_calls": all_tool_calls}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
