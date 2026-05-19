# Strategic Development Roadmap

This roadmap defines how Echolace LLM Router can outperform routing competitors by owning two positions they do not: deep enterprise privacy and hardware-adaptive intelligence.
The goal is not to become a thinner router with more providers.
The goal is to become the policy engine that decides where AI workloads should run, why they should run there, and how to prove that decision was safe.

---

## Implementation Status

This document started as a strategic target.
It is no longer purely aspirational.
As of the current codebase, the core technical pillars are partially to substantially implemented.

### Implemented now

- `LLMInterface` has a real policy-driven routing layer in [`router.py`](../llm_router/router.py).
- Privacy-aware routing is live through [`policies/privacy_guard.py`](../llm_router/policies/privacy_guard.py), [`security/pii.py`](../llm_router/security/pii.py), [`security/redaction.py`](../llm_router/security/redaction.py), and [`security/vault.py`](../llm_router/security/vault.py).
- Strict-local and hybrid-redacted privacy execution modes are implemented.
- Structured nested payloads and chat-style message lists are scanned by the privacy layer before cloud routing.
- Semantic intent routing is implemented through [`intent.py`](../llm_router/intent.py) and [`policies/intent_router.py`](../llm_router/policies/intent_router.py).
- `llm.intent()` is live and uses semantic retrieval with thresholds, expanded taxonomy, tenant schemas, and route-regret tracking.
- Hardware-adaptive telemetry and routing support are implemented through [`telemetry/hardware_monitor.py`](../llm_router/telemetry/hardware_monitor.py), [`telemetry/benchmark_store.py`](../llm_router/telemetry/benchmark_store.py), and [`policies/route_planner.py`](../llm_router/policies/route_planner.py).
- Continuous canary benchmarking, rolling TTFT and tokens/sec tracking, queue-depth-aware viability, downgrade recommendations, and optional SQLite telemetry persistence are implemented.
- `llm.heal()` is live and now produces richer remediation plans through [`healing/planner.py`](../llm_router/healing/planner.py).
- Healing paths now cover Ollama, GGUF, LM Studio, GPT4All, and Hugging Face local remediation.
- Automated pytest coverage exists for privacy routing, structured payload handling, semantic intent routing, hardware benchmarking, downgrade logic, and healing behavior.

### Still not complete

- No hosted enterprise control plane or fleet-management layer exists in this repository.
- No persistent encrypted vault or external KMS integration is implemented yet.
- Compliance packs are still lightweight profiles rather than fully audited policy bundles.
- The intent system does not yet ship a second-stage local re-ranker.
- Business and go-to-market items in this document remain strategic, not code deliverables.

### How to read the rest of this roadmap

Treat the remaining sections as a mix of:

- architecture that now exists in code
- capabilities that are partially implemented and need hardening
- future product and enterprise work that still needs to be built

---

## North Star

**Positioning**

Echolace should be known as:

**The only open AI router that protects sensitive data by default and adapts to the hardware it is running on in real time.**

This creates a differentiated wedge in regulated and privacy-conscious environments:

- legal
- healthcare
- finance
- defense-adjacent
- enterprise copilots on managed laptops
- edge devices with intermittent connectivity

The existing architecture already provides a useful base:

- [`LLMInterface`](../llm_router/router.py) is the public control surface.
- [`diagnostics.py`](../llm_router/diagnostics.py) is the natural place to add hardware telemetry and repair planning.
- provider modules remain isolated, which is ideal for policy-driven orchestration above them.

The next stage is to add a policy layer, not a provider explosion.

---

## 1. Competitive Gaps and Strategic Response

### ClawRouter gap: no serious privacy-first local fallback

ClawRouter emphasizes payment flow and agent-native logic, but that is not enough for enterprise adoption.
Enterprises do not merely want optional privacy.
They want a system that assumes sensitive content is present, proves it was handled correctly, and degrades safely.

**Echolace response**

Build a local-first interception layer called **Privacy Vault**:

- inspect prompts before provider selection
- detect PII, secrets, credentials, and regulated entities locally
- replace sensitive spans with structured placeholders
- keep original values in an ephemeral local vault
- route redacted context to cloud models only when policy permits
- rehydrate or finalize responses locally when exact values are required
- emit an auditable routing decision record for each request

This changes the product from "model switchboard" to "data-governance-aware inference fabric."

### Not Diamond gap: proprietary, SaaS-first, weak transparency

Not Diamond wins on smart routing, but its proprietary posture limits trust with engineering teams that want inspectability, self-hosting, and control.

**Echolace response**

Use open-source principles as a product feature:

- publish routing policy interfaces and scoring logic
- keep providers, policies, and telemetry adapters as pluggable modules
- expose trace events for every routing decision
- support fully local evaluation harnesses
- ship reference policies that users can fork instead of opaque black-box rankings

This creates a strong open alternative for developers who want to know why the router made a decision and how to change it.

---

## 2. Technical Improvement Roadmap

## Pillar A: Privacy Vault

### Objective

Intercept requests locally, detect sensitive data, and route by sensitivity rather than by provider availability alone.

### Proposed architecture

Add a policy pipeline above the current backend selector:

```text
Application
  -> LLMInterface.generate()
  -> RequestPolicyEngine
      -> PiiInspector
      -> SecretDetector
      -> IntentClassifier
      -> HardwareMonitor
      -> RoutePlanner
  -> Selected backend(s)
  -> ResponsePostProcessor
  -> Final response
```

### New modules

Recommended package layout:

```text
llm_router/
  policies/
    __init__.py
    engine.py
    privacy_guard.py
    intent_router.py
    route_planner.py
  security/
    pii.py
    vault.py
    redaction.py
  telemetry/
    hardware_monitor.py
    benchmark_store.py
  healing/
    planner.py
```

### Privacy Vault request flow

1. `LLMInterface.generate()` accepts raw prompt or message list.
2. `PiiInspector` runs locally using Microsoft Presidio plus deterministic regex detectors for:
   - SSNs
   - phone numbers
   - email addresses
   - names
   - addresses
   - account numbers
   - API keys
   - bearer tokens
   - SSH private key headers
   - internal ticket IDs and tenant IDs
3. Detected spans are scored by risk level:
   - `public`
   - `internal`
   - `confidential`
   - `regulated`
4. Sensitive spans are replaced with placeholders such as `<PERSON_1>` or `<API_KEY_1>`.
5. The original spans are stored in an in-memory encrypted vault object keyed by request ID.
6. `RoutePlanner` selects one of three execution modes:
   - `strict_local`: full request stays local
   - `hybrid_redacted`: redacted request goes to cloud, rehydration stays local
   - `cloud_allowed`: no significant sensitivity detected
7. Response assembly happens locally:
   - redact unsafe model echoes
   - optionally reinsert allowed placeholders
   - attach audit metadata

### Why hybrid routing is viable

The cloud model does not need raw PII for many tasks:

- summarization
- classification
- formatting
- drafting
- extraction
- transformation

For those tasks, the cloud sees a semantically intact redacted prompt.
If the final output requires exact sensitive values, a local post-processor can rehydrate placeholders or run a second local pass over the cloud draft.

Example:

- input: "Draft a client update for Jane Doe, SSN 123-45-6789, regarding case 21-8841."
- cloud sees: "Draft a client update for `<PERSON_1>`, `<SSN_1>`, regarding case `<CASE_ID_1>`."
- local vault stores the original values.
- local post-processor decides whether placeholders may be restored in the output based on policy.

### Integration with existing systems

The cleanest integration point is [`LLMInterface`](../llm_router/router.py):

- add a `policy_engine` field initialized in `__init__`
- wrap `generate()` and `stream()` with a planning step before backend execution
- preserve provider modules as execution endpoints, not policy owners

Recommended `LLMInterface` extension:

```python
class LLMInterface:
    def __init__(
        self,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        privacy_first: bool = False,
        intent_routing: bool = False,
        hardware_adaptive: bool = False,
        local_privacy_backend: str = "ollama",
        local_privacy_model: Optional[str] = None,
        policy_engine: Optional["RequestPolicyEngine"] = None,
        **kwargs,
    ):
        ...
```

### Security design choices

- default vault storage should be memory-only
- optional persistent vault should use OS keystore or enterprise KMS
- audit records should never store raw secrets
- policy evaluation should happen before any network call
- privacy rules should support tenant-specific overrides

### Phase delivery

**Phase 1**

- Presidio integration
- regex-based secret detectors
- redaction placeholders
- strict-local policy mode

**Phase 2**

- hybrid redacted routing
- response rehydration
- audit log export
- configurable privacy policies by tenant or workspace

**Phase 3**

- document-level sensitivity profiles
- policy packs for HIPAA, PCI, SOC 2, GDPR
- field-aware protection for structured JSON payloads

---

## Pillar B: Semantic Intent Mapping

### Objective

Replace simple provider fallback with task-aware model routing.
The router should infer what the user is asking for, then pick the best model family for that workload.

### Design principle

Do not start with a heavyweight classifier.
Start with an embedding-first policy engine that is local, inspectable, and easy to improve from user telemetry.

### Recommended architecture

Use a two-stage classifier:

1. **Embedding retrieval**
   - embed the incoming prompt with a local embedding model
   - compare it to an intent library in a vector index
2. **Lightweight re-ranker**
   - use a small local instruct model to resolve ambiguous intents and multi-intent prompts

This balances speed and accuracy while staying fully open.

### Suggested intent taxonomy

Initial labels should be operational, not academic:

- `coding`
- `debugging`
- `summarization`
- `structured_extraction`
- `creative_writing`
- `translation`
- `reasoning`
- `rag_qa`
- `sensitive_business_content`
- `vision_multimodal`
- `tool_use_or_agentic`
- `low_latency_chat`

Each intent maps to a routing policy, not just a single model.

Example:

- `coding` -> prefer Claude Sonnet or strong code-tuned local model
- `summarization` -> prefer low-cost fast model
- `sensitive_business_content` -> prefer local-first unless explicit override
- `low_latency_chat` -> prefer smallest model meeting quality threshold

### Datasets and tools

Use a staged data strategy:

**Bootstrapping datasets**

- `HuggingFaceH4/ultrachat_200k` for general assistant prompts
- `Open-Orca/OpenOrca` for instruction diversity
- `iamtarun/code_instructions_120k_alpaca` or `CodeAlpaca-20k` for coding prompts
- `cnn_dailymail` and `xsum` for summarization task framing
- `opus100` or `FLORES-200` prompt templates for translation
- internal synthetic prompt generation to create privacy-heavy enterprise examples

**Tools**

- `sentence-transformers` for local embeddings
- `faiss` or `sqlite-vss` for vector retrieval
- `scikit-learn` for calibration baselines
- `transformers` for the lightweight local re-ranker
- `mlflow` or a simple JSONL eval harness for route-quality tracking

### Model recommendation

Keep the first release practical:

- embeddings: `bge-small-en-v1.5` or `nomic-embed-text`
- re-ranker: a small Qwen-class instruct model in the 1.5B to 1.8B range

This remains deployable on modest hardware and aligns with the router's local-first thesis.

### Training and deployment plan for `llm.intent()`

1. Define the intent taxonomy and routing targets.
2. Collect seed prompts from public datasets and label them by task intent.
3. Generate synthetic enterprise prompts for privacy-sensitive classes.
4. Train a baseline embedding classifier using centroid matching or logistic regression over embeddings.
5. Add a local re-ranker for prompts with low-confidence or multi-label scores.
6. Evaluate on:
   - intent accuracy
   - route regret
   - median latency
   - cost per request
   - privacy policy violations
7. Package the model artifacts locally:
   - embeddings config
   - vector index
   - calibration thresholds
   - model-to-intent routing map
8. Expose a public API:

```python
intent = llm.intent("Refactor this Python function and add unit tests.")
# {
#   "label": "coding",
#   "confidence": 0.93,
#   "candidate_labels": ["coding", "debugging"],
#   "recommended_backend": "anthropic",
#   "recommended_model": "claude-3-5-sonnet"
# }
```

9. Log intent predictions with opt-in telemetry and compare predicted route vs actual user satisfaction.
10. Fine-tune thresholds continuously from anonymized or self-hosted customer feedback loops.

### Actionable implementation steps

- create `intent_router.py` with a pluggable classifier interface
- ship a rules-plus-embeddings MVP first
- add `llm.intent()` before turning on automatic intent routing by default
- support user overrides so routing remains deterministic when needed

---

## Pillar C: Hardware-Adaptive Dynamic Benchmarking

### Objective

Make routing aware of the actual machine state, not just static model capability.

This is the strongest technical wedge against both competitors because it turns local inference from a binary yes-or-no check into a continuously optimized execution decision.

### Real-time monitoring design

Extend [`diagnostics.py`](../llm_router/diagnostics.py) into a lightweight telemetry layer with rolling metrics:

- CPU utilization
- CPU frequency drift
- system memory pressure
- swap usage
- GPU utilization
- GPU VRAM headroom
- thermal status if exposed by platform APIs
- queue depth for local inference backends
- rolling tokens/sec per local model
- time-to-first-token
- p95 end-to-end latency

### Cross-platform collection method

**CPU and memory**

- `psutil` for load, memory, swap, and basic temperature where available

**NVIDIA**

- `pynvml` or `nvidia-smi --query-gpu`

**AMD**

- `rocm-smi` parsing when available

**Apple Silicon**

- `powermetrics` integration where permitted
- fallback to `torch.mps` availability and observed local model throughput

**Backend-level benchmarking**

- run short canary prompts periodically against each local backend
- store moving averages for latency and tokens/sec
- use EWMA windows so routing reacts quickly without oscillation

### Dynamic routing policy

Compute a **local viability score** for every local-capable backend:

```text
local_viability =
  quality_weight * benchmark_score
  + privacy_weight * policy_priority
  + availability_weight * model_ready
  - thermal_penalty
  - memory_penalty
  - queue_penalty
```

If the machine is under load or throttling:

- move from large local model -> smaller local model
- or from local -> cloud
- except when privacy policy requires strict-local execution

This keeps latency predictable without violating privacy guarantees.

### Dynamic routing examples

- laptop on battery with rising thermals: route summarization to cloud, keep PII prompts local
- desktop workstation idle with ample VRAM: route coding tasks to strong local model
- edge server nearing VRAM exhaustion: downgrade to quantized local model before failing over to cloud

### Actionable implementation steps

- add `telemetry/hardware_monitor.py`
- add background sampler with opt-in interval, for example 2 to 5 seconds
- persist rolling metrics in memory and optional local SQLite
- expose `llm.hardware_status()` for inspection
- incorporate telemetry scores into backend selection and `best_backend()`

---

## 3. Open-Source Positioning and Business Strategy

### Open-source product thesis

Echolace should compete on trust and controllability:

- open routing policies
- open audit event schema
- self-hosted deployment paths
- local-first privacy enforcement
- enterprise extensions for control plane, compliance, and fleet management

This is a better wedge than racing to pure benchmark parity.

### Product-led growth model

**Open core**

- free local and cloud backend routing
- free diagnostics
- free basic intent classification
- free local policy engine

**Enterprise paid layers**

- managed privacy control plane
- fleet policy management
- encrypted audit retention
- compliance templates
- model approval workflows
- SSO, SCIM, and tenant administration
- signed enterprise builds and long-term support

### Additional monetization strategies

- **Compliance packs**: paid HIPAA, PCI, GDPR, FINRA, CJIS policy bundles
- **Private model registry**: managed catalog of approved GGUF, Ollama, and cloud model profiles
- **Enterprise support SLAs**: architecture review, performance tuning, incident response
- **On-prem appliance edition**: preconfigured workstation or server image for air-gapped deployments
- **Routing analytics**: cost, latency, and privacy posture dashboards
- **Marketplace revenue share**: partner-certified policies, detectors, and backend plugins
- **Red-team service**: paid prompt leakage and policy bypass testing

### Strategic partnerships

- hardware vendors: Dell, Lenovo, HP, Framework workstation channels
- GPU ecosystem: NVIDIA, AMD, Intel edge AI teams
- privacy/security platforms: Microsoft Purview, CrowdStrike, Palo Alto Networks, Wiz
- model serving vendors: Ollama ecosystem, llama.cpp distributions, vLLM integrators
- systems integrators focused on legal, healthcare, and public sector deployments

### Category creation

Do not market Echolace as just another router.
Market it as:

**Private inference orchestration for enterprises that cannot treat prompts as harmless text.**

---

## 4. Immediate Product Surface Additions

## `llm.heal()` function prototype

This should expand diagnostics into a guided repair planner.
It must preserve the project's transparency principle, so destructive or networked actions should remain explicit.

```python
from typing import Any, Dict, List, Optional


class LLMInterface:
    def heal(
        self,
        apply: bool = False,
        allow_network: bool = False,
        install_python_deps: bool = False,
        pull_models: bool = False,
        prefer_local: bool = True,
        backend: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Diagnose missing dependencies, model assets, and backend reachability,
        then return or optionally execute a repair plan.

        Returns:
            {
                "healthy": bool,
                "selected_backend": str,
                "issues": List[Dict[str, Any]],
                "plan": List[Dict[str, Any]],
                "applied": List[Dict[str, Any]],
                "skipped": List[Dict[str, Any]],
            }
        }
        """
        ...
```

### `llm.heal()` responsibilities

- call diagnostics for all backends
- identify missing Python packages
- identify missing local model artifacts
- detect inactive local servers such as Ollama or LM Studio
- propose exact repair steps:
  - `pip install anthropic`
  - `ollama pull qwen2.5:7b`
  - download GGUF to configured path
  - set required environment variables
- optionally execute safe actions when flags permit
- write a repair report for support and automation

### Suggested repair-plan schema

```python
{
    "backend": "ollama",
    "issue": "model_missing",
    "severity": "warning",
    "action": "pull_model",
    "command": ["ollama", "pull", "qwen2.5:7b"],
    "requires_network": True,
    "auto_applicable": True,
}
```

## `llm.intent()` rollout

Recommended public method:

```python
class LLMInterface:
    def intent(
        self,
        prompt: str,
        top_k: int = 3,
        include_route: bool = True,
    ) -> Dict[str, Any]:
        """Return predicted task intent and the recommended route."""
        ...
```

### Deployment sequence

1. Ship `llm.intent()` as read-only introspection.
2. Add `intent_routing=True` as an opt-in automatic planner.
3. Log route outcomes and misclassifications.
4. Turn on per-intent backend defaults.
5. Add tenant-custom intent schemas for enterprise customers.

## Privacy Mode code sketch

One-line configuration should be enough to make privacy the default:

```python
from llm_router import LLMInterface

llm = LLMInterface(
    privacy_first=True,
    local_privacy_backend="ollama",
    local_privacy_model="qwen2.5:7b",
    hardware_adaptive=True,
)

response = llm.generate(
    "Summarize this patient update for Jane Doe at 742 Evergreen Terrace, "
    "member ID 8821901, but keep all regulated data local."
)
```

### Expected policy behavior

- detect PII locally
- redact before any cloud call
- keep sensitive values in local vault
- route either strict-local or hybrid-redacted
- emit decision metadata for observability

---

## 5. 90-Day Execution Plan

### Days 0-30: Foundation

- add policy engine abstraction
- integrate Presidio plus regex secret detectors
- add privacy-first config surface
- extend diagnostics into repair planning
- create benchmark harness for local backends

### Days 31-60: Intelligence

- release `llm.intent()` MVP
- train initial intent taxonomy
- add hybrid redacted routing
- record latency, TTFT, and tokens/sec for local backends
- publish routing trace schema

### Days 61-90: Enterprise differentiation

- add hardware-adaptive routing loop
- add audit export and compliance presets
- ship hosted control plane design for fleet policies
- publish benchmark report comparing:
  - cloud-only routing
  - naive local fallback
  - Echolace privacy-aware adaptive routing

Success should be measured on:

- lower privacy leakage risk
- lower median latency under local load
- lower cost per acceptable response
- better transparency than SaaS-first competitors

---

## 6. Final Strategic Thesis

ClawRouter can own agent-native payment logic.
Not Diamond can own SaaS optimization narratives.
Echolace should own the intersection of:

- privacy
- transparency
- hardware awareness
- local-first control

That is not a narrow niche.
That is the infrastructure layer enterprises will need when they stop asking which model is smartest and start asking which routing system can be trusted.
