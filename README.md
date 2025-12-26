# Copy and Paste for AI Agents: An Experimental Primitive

**TL;DR:** We gave an AI agent clipboard semantics—`copy` to extract content into named slots, `template_invoke` to substitute that content into tool calls without regenerating it. The agent adopted the pattern naturally and executed clipboard workflows reliably across extraction methods and tool compositions. This eliminates three compounding problems: token waste (content isn't regenerated), latency (no time spent producing tokens that already exist), and mutation risk (content stays byte-for-byte identical because it never passes through the LLM).

---

## The Problem

When AI agents call tools, they regenerate content they've already seen. An agent reads a file, holds it in context, then writes it back out token-by-token into a tool parameter. This creates token waste, latency, and mutation risk—the content might get subtly altered each time it passes through the LLM.

Humans solved this decades ago with copy and paste. Agents have no equivalent primitive.

## The Experiment

We built a minimal harness with two tools:

- **`copy`** extracts content from tool results into named clipboard slots using regex patterns, line ranges, or JSON paths. The harness stores the content—it never flows through the LLM's generation path.

- **`template_invoke`** executes tool calls with `{{slot}}` placeholders. The harness resolves placeholders from the clipboard and dispatches the fully-formed call. The agent declares *what* goes *where*; the harness moves the actual bytes.

We ran functional tests against Claude Sonnet 4, prompting the agent to read files, extract specific content, and use that content in subsequent tool calls.

## Results

**The agent understood the workflow immediately.** Without explicit instruction, it consistently executed read → copy → template_invoke pipelines. When asked to "extract lines 7-10 into a slot, then create a new file with that content," it did exactly that.

**Extraction method selection was appropriate.** The agent correctly mapped prompt cues to extraction parameters—"lines X-Y" triggered line-based extraction, "using a pattern" triggered regex, and requests for entire files omitted extraction parameters entirely.

**Line-based extraction was completely reliable.** Every test using `start_line`/`end_line` parameters produced correct results with the expected byte counts.

**Pattern extraction succeeded for semantic targets.** When asked to extract the `main` function from a Python file, the agent constructed a multiline regex (`def main\(\):.*?^(?=\S|\Z)`) that correctly captured 506 bytes—the full function definition including docstring and body.

**Self-correction emerged naturally.** In one test, the agent's initial regex only captured one import statement (9 bytes). It recognized the result was insufficient, refined the pattern, and correctly captured both imports (20 bytes) on the second attempt.

**Template composition worked as designed.** The agent combined multiple slots with formatting (`"{{imports}}\n\n{{helper}}"`) and used slots across different target tools—`create_file` for writing extracted code, `http_request` for sending file contents to APIs.

**Full-content copying required no special handling.** When asked to copy an entire file, the agent correctly omitted extraction parameters, and the harness stored all 731 bytes for later substitution.

**Token savings were measurable.** In a representative test extracting and reusing a 500-byte function, the clipboard pattern saved approximately 122 output tokens—a 38% reduction compared to the agent regenerating the content. The overhead of slot references (`{{slot_name}}`) was negligible at ~3 tokens. Savings scale with content size and reuse frequency.

**Mutation risk was eliminated.** Because content flows from clipboard to tool invocation without passing through LLM token generation, the extracted content remains byte-for-byte identical. The agent declares intent; the harness moves the actual bytes. For tasks requiring verbatim preservation—code, configurations, legal text, API payloads—this guarantee is critical.

## The Key Finding

The agent didn't need to be taught clipboard semantics. Given tools with clear extraction and substitution mechanics, it naturally adopted the pattern. The cognitive overhead concern—that agents would find clipboard indirection confusing—didn't materialize.

This suggests clipboard primitives belong in the standard agent tooling vocabulary.

## Implications for Harness Developers

This cannot be implemented as a standalone MCP server. The substitution must happen at the harness layer—after the agent declares its intent but before content flows through token generation. An MCP server can store clipboard state, but it cannot prevent the LLM from re-synthesizing content when calling other tools.

The pattern enables verbatim content preservation, reduced token generation, and composable extraction-to-action workflows. Agents adopt it without friction.

## Next Steps

This experiment validated that agents naturally adopt clipboard semantics. Further work could strengthen these findings:

**Generic system prompts.** Our experiment used a system prompt tailored to clipboard tool usage. Testing with a general-purpose agent prompt—where the agent must discover when clipboard tools are appropriate rather than being guided toward them—would better validate natural adoption and reveal how agents decide between direct content generation and clipboard indirection.

**Quantitative benchmarking.** Run controlled comparisons across varied content sizes (1KB to 100KB), measuring token usage, latency, and output fidelity with and without clipboard tools. Establish clear ROI curves for different use cases.

**Multi-step workflows.** Test clipboard persistence across longer agent tasks—does the pattern hold when an agent extracts content early in a workflow and reuses it 10+ tool calls later? How do agents manage slot naming and cleanup?

**Multi-agent handoffs.** Explore shared clipboard state between agents. Can one agent extract content and another consume it via `template_invoke`? What coordination patterns emerge?

**Mutation risk validation.** Systematically compare output fidelity—run identical tasks with and without clipboard tools on content where even single-character changes matter (code, JSON configs, legal text) and quantify error rates.

---

## Usage

### Installation

```bash
pip install -r requirements.txt
```

### Configuration

Copy the environment template and add your API key:

```bash
cp .env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### Running the Agent

```bash
python run.py "Read example.py, extract the main function, and save it to extracted.py"
```

Options:
- `-v, --verbose` — Enable debug logging
- `--model MODEL` — Specify model (default: claude-sonnet-4-20250514)
- `--no-log` — Disable JSON test logging

---

## License

MIT

---

*Experiment conducted December 2025.*
