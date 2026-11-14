"""Claude calls, plus a meter that records the tokens and cost of every call."""
import anthropic

STRONG = "claude-opus-5-5"   # splits the claim, writes the verdict (short, hard steps)
CHEAP = "claude-haiku-5-5"   # scores results, trims pages (high-volume, simple steps)

# $ per 1M tokens: (input, output)
PRICES = {STRONG: (4.00, 20.00), CHEAP: (0.10, 0.50)}

_client = None


def client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    return _client


class Meter:
    """One line per LLM call: step, model, input tokens, output tokens, cost."""

    def __init__(self):
        self.calls = []

    def add(self, step, model, usage):
        price_in, price_out = PRICES.get(model, PRICES[STRONG])
        cost = (usage.input_tokens * price_in + usage.output_tokens * price_out) / 1e6
        self.calls.append({"step": step, "model": model, "input": usage.input_tokens,
                           "output": usage.output_tokens, "cost": round(cost, 5)})

    def total(self, key, steps=None):
        return sum(c[key] for c in self.calls if steps is None or c["step"] in steps)


def ask(meter, step, prompt, schema, model=CHEAP, system=None):
    """Ask Claude and get the answer back as a filled-in `schema` object."""
    kwargs = dict(model=model, messages=[{"role": "user", "content": prompt}],
                  output_format=schema)
    if system:
        kwargs["system"] = system
    if model == STRONG:
        # If Opus declines a request, the API retries it on a fallback model.
        resp = client().beta.messages.parse(
            max_tokens=16000, output_config={"effort": "medium"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
    else:
        resp = client().messages.parse(max_tokens=8000, output_config={"effort": "low"}, **kwargs)
    meter.add(step, resp.model, resp.usage)
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"{step}: the model declined this request")
    if resp.parsed_output is None:
        raise RuntimeError(f"{step}: no usable answer (stop reason: {resp.stop_reason})")
    return resp.parsed_output


def count_tokens(system, prompt):
    """How many tokens Opus WOULD read for this prompt, without running it."""
    try:
        return client().messages.count_tokens(
            model=STRONG, system=system,
            messages=[{"role": "user", "content": prompt}]).input_tokens, "counted"
    except anthropic.APIStatusError:
        return len(system + prompt) // 4, "estimated"  # too large to count: ~4 chars per token
