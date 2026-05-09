"""
Deep Learning Analyzer — studies the extracted module representation and
produces classified understanding: purpose, callable actions, environment
requirements, expansion potential, and confidence scores.

Uses a lightweight heuristic + keyword model that simulates DL classification
without requiring a GPU or large model download. The architecture is designed
so a real transformer model (e.g. sentence-transformers) can be swapped in
by replacing the _classify_* methods.
"""
import re
import time
from typing import Any, Dict, List, Tuple

from core.event_bus import Severity, bus
from core.module_state import ModuleStage, registry


# ---------------------------------------------------------------------------
# Category taxonomy
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "data_processing":   ["dataframe", "pandas", "csv", "etl", "transform", "pipeline", "batch"],
    "api_service":       ["fastapi", "flask", "django", "endpoint", "route", "rest", "http", "request"],
    "machine_learning":  ["torch", "tensorflow", "model", "train", "predict", "inference", "embedding"],
    "nlp":               ["nlp", "text", "tokenize", "language", "bert", "gpt", "llm", "prompt"],
    "computer_vision":   ["image", "cv2", "opencv", "vision", "detect", "yolo", "pixel"],
    "database":          ["sql", "postgres", "mongo", "redis", "query", "orm", "migration"],
    "automation":        ["schedule", "cron", "task", "automate", "workflow", "trigger"],
    "monitoring":        ["monitor", "watchdog", "alert", "metric", "health", "log", "trace"],
    "communication":     ["websocket", "kafka", "rabbitmq", "pubsub", "stream", "event", "message"],
    "utility":           ["util", "helper", "common", "shared", "tool", "format", "parse"],
}

ENVIRONMENT_KEYWORDS = {
    "torch_env":   ["torch", "cuda", "gpu", "tensorflow", "model", "train", "inference"],
    "fastapi_env": ["fastapi", "uvicorn", "starlette", "endpoint", "api", "rest"],
    "gpu_env":     ["cuda", "gpu", "nvidia", "cupy", "rapids"],
    "cpu_env":     [],  # fallback
}


def _flatten_text(data: Any, depth: int = 0) -> str:
    """Recursively flatten any structure to a single text blob."""
    if depth > 6:
        return ""
    if isinstance(data, str):
        return data.lower()
    if isinstance(data, dict):
        return " ".join(_flatten_text(v, depth + 1) for v in data.values())
    if isinstance(data, list):
        return " ".join(_flatten_text(i, depth + 1) for i in data)
    return str(data).lower()


def _score_keywords(text: str, keywords: List[str]) -> float:
    count = sum(1 for kw in keywords if kw in text)
    return round(count / max(len(keywords), 1), 3)


def _classify_purpose(text: str) -> Tuple[str, float]:
    scores = {cat: _score_keywords(text, kws) for cat, kws in CATEGORY_KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best, scores[best]


def _classify_environment(text: str, env_defs: dict) -> str:
    # Check explicit env definitions first
    for env_name in env_defs:
        for key in ENVIRONMENT_KEYWORDS:
            if key.replace("_env", "") in env_name.lower():
                return key
    # Fall back to keyword scoring
    scores = {}
    for env, kws in ENVIRONMENT_KEYWORDS.items():
        if not kws:
            continue
        scores[env] = _score_keywords(text, kws)
    if scores:
        best = max(scores, key=scores.get)
        if scores[best] > 0:
            return best
    return "cpu_env"


def _extract_callable_actions(capabilities: dict) -> List[Dict]:
    """Parse capabilities.json into a ranked list of callable actions."""
    actions = []
    if isinstance(capabilities, dict):
        # Support both flat and nested formats
        items = capabilities.get("capabilities", capabilities.get("actions", capabilities))
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    actions.append({
                        "name": item.get("name", item.get("action", "unknown")),
                        "description": item.get("description", ""),
                        "inputs": item.get("inputs", item.get("input_types", [])),
                        "outputs": item.get("outputs", item.get("output_types", [])),
                        "confidence": 0.95,
                    })
        elif isinstance(items, dict):
            for name, details in items.items():
                if isinstance(details, dict):
                    actions.append({
                        "name": name,
                        "description": details.get("description", ""),
                        "inputs": details.get("inputs", []),
                        "outputs": details.get("outputs", []),
                        "confidence": 0.90,
                    })
                else:
                    actions.append({"name": name, "description": str(details), "inputs": [], "outputs": [], "confidence": 0.85})
    return actions


def _score_expansion_potential(actions: List[Dict], text: str) -> float:
    """Score how much this module can expand the global capability registry."""
    base = min(len(actions) * 0.1, 0.5)
    hook_bonus = 0.2 if "hook" in text or "expand" in text or "plugin" in text else 0.0
    return round(min(base + hook_bonus + 0.3, 1.0), 2)


def _extract_communication_patterns(text: str) -> List[str]:
    patterns = []
    pattern_map = {
        "request_response": ["request", "response", "reply", "answer"],
        "event_driven":     ["event", "emit", "subscribe", "publish", "listen"],
        "streaming":        ["stream", "chunk", "yield", "generator", "async"],
        "batch":            ["batch", "bulk", "queue", "schedule"],
    }
    for pattern, kws in pattern_map.items():
        if any(kw in text for kw in kws):
            patterns.append(pattern)
    return patterns or ["request_response"]


def analyze(module_id: str, extracted: Dict[str, Any]) -> Dict[str, Any]:
    """
    Full deep learning analysis pipeline.
    Returns analyzer output dict.
    """
    emit = lambda msg, sev=Severity.INFO: bus.emit(
        "DEEP LEARNING ANALYZER", msg, sev, module_id=module_id
    )

    registry.update_stage(module_id, ModuleStage.ANALYZING)
    emit("🧠  Deep learning analyzer active")
    time.sleep(0.3)  # Simulate analysis time

    # Build full text corpus from all extracted data
    corpus = _flatten_text(extracted)

    emit("🎯  Classifying module purpose")
    purpose, purpose_confidence = _classify_purpose(corpus)

    emit("🔎  Identifying callable actions")
    actions = _extract_callable_actions(extracted.get("capabilities", {}))

    # Also scan intents for additional action hints
    intents_data = extracted.get("intents", {})
    intent_list = []
    if isinstance(intents_data, dict):
        raw_intents = intents_data.get("intents", intents_data.get("mappings", intents_data))
        if isinstance(raw_intents, list):
            intent_list = raw_intents
        elif isinstance(raw_intents, dict):
            intent_list = [{"label": k, **v} if isinstance(v, dict) else {"label": k, "action": v}
                           for k, v in raw_intents.items()]

    emit("📊  Scoring expansion potential")
    expansion_score = _score_expansion_potential(actions, corpus)

    emit("🖥️   Determining environment requirements")
    recommended_env = _classify_environment(corpus, extracted.get("env_defs", {}))

    emit("🔗  Analyzing communication patterns")
    comm_patterns = _extract_communication_patterns(corpus)

    # Build task relationships from routes
    routes_data = extracted.get("routes", {})
    task_relationships = []
    if isinstance(routes_data, dict):
        raw_routes = routes_data.get("routes", routes_data.get("paths", routes_data))
        if isinstance(raw_routes, list):
            task_relationships = [r.get("name", str(r)) if isinstance(r, dict) else str(r) for r in raw_routes]
        elif isinstance(raw_routes, dict):
            task_relationships = list(raw_routes.keys())

    emit("✅  Analysis complete", Severity.SUCCESS)

    result = {
        "module_id": module_id,
        "classified_purpose": purpose,
        "purpose_confidence": purpose_confidence,
        "callable_actions": actions,
        "intent_mappings": intent_list,
        "communication_patterns": comm_patterns,
        "task_relationships": task_relationships,
        "recommended_environment": recommended_env,
        "expansion_potential_score": expansion_score,
        "capability_confidence_ratings": {a["name"]: a["confidence"] for a in actions},
        "analysis_timestamp": time.time(),
    }

    # Update registry with analyzer output
    registry.update_field(module_id, analyzer_output=result)

    return result
