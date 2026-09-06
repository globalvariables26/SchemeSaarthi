# LangGraph — a 10-minute primer (read before touching agents/orchestrator.py)

You don't need to read LangGraph's full docs to work on this project. Here's the minimum
mental model, mapped directly to what's already built in `agents/orchestrator.py`.

## The core idea

A LangGraph graph is just: **nodes** (functions that take state, do something, return updated
state) + **edges** (which node runs next). That's it. It's a state machine with a nicer API
than writing your own `while` loop of `if/elif`.

```python
graph = StateGraph(GraphState)          # GraphState = our Pydantic model (agents/state.py)
graph.add_node("consent", consent_fn)   # register a node with a name
graph.add_node("discovery", discovery_fn)
graph.set_entry_point("consent")        # where the graph starts
graph.add_edge("consent", "discovery")  # unconditional: consent always leads to discovery
compiled = graph.compile()              # turns the graph definition into something runnable
result = compiled.invoke(initial_state) # actually runs it, returns final state
```

## Where "orchestration" actually lives

There is no single "Orchestrator" function that calls the other 6 agents in sequence like a
normal Python script would. Instead, the **routing itself** — decided by
`add_conditional_edges` — IS the Orchestrator. Look at `_route_after_discovery` in
`orchestrator.py`:

```python
def _route_after_discovery(state: GraphState) -> Literal["matching", "notify_and_end"]:
    result = state.node_results.get("DiscoveryAgent")
    if result and result.status == "failed":
        return "notify_and_end"   # skip straight to Notification Agent, don't try to match
    return "matching"             # normal path
```

This function runs automatically after the `discovery` node finishes. It reads what Discovery
just wrote to `state.node_results`, and decides which node runs next. **This is the
"re-planning" the hackathon rubric wants to see** — it's not a metaphor, it's a real branch in
the actual control flow, which is exactly why LangGraph was chosen over a plain linear script.

## Why state is a Pydantic model, not a dict

Every node receives the FULL current state and returns the FULL updated state (in this
codebase — some LangGraph patterns return partial diffs instead, but we're using the simpler
"mutate and return the whole object" style since our nodes already do that). Because
`GraphState` (in `agents/state.py`) is a Pydantic model, if a node tries to write a field with
the wrong type, you get a loud error immediately instead of silent corruption three nodes
later.

## How to actually debug this

1. Run one node function directly, outside the graph, first:
   ```python
   from agents.state import GraphState, TriggerType
   from agents.context import build_context
   from agents.nodes import consent_agent

   ctx = build_context()
   state = GraphState(citizen_id="<id>", trigger=TriggerType.MANUAL_DEMO_TRIGGER)
   state = consent_agent.run(state, ctx)
   print(state.node_results["ConsentProfileAgent"])
   ```
   This bypasses LangGraph entirely and just calls the Python function — the fastest way to
   find a bug in one agent's logic without running the whole graph every time.

2. Once individual nodes work, run the compiled graph (`agents/orchestrator.py`'s
   `run_graph_for_citizen`) and inspect `state.node_results` (what each agent decided) and
   `state.replan_events` (when/why the Orchestrator deviated from the default path).

3. If the graph itself won't even build (`get_graph()` throws), the error is almost always one
   of: (a) a node name in `add_conditional_edges`'s mapping dict that doesn't match an actual
   `add_node` name, or (b) a missing edge — every node needs a way to eventually reach `END`.

## What you do NOT need to learn for this project

- LangGraph's checkpointing/persistence features (SqliteSaver, etc.) — not used here; we
  persist everything ourselves directly to Supabase inside each node.
- LangGraph's built-in agent/tool-calling abstractions — our LLM calls go straight through
  `agents/llm_client.py` to Groq, not through LangGraph's own agent wrappers. Simpler, and
  keeps the JSON-mode structured output fully under our control.
- Async graphs — everything here runs synchronously (`.invoke()`, not `.ainvoke()`), which is
  fine for a hackathon demo's request volume.
