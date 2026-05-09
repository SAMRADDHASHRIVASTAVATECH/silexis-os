"""Internal routing logic."""


class Router:
    def route(self, intent: str, payload: dict) -> str:
        routes = {
            "classify_text":    "executor.run_classifier",
            "analyze_sentiment":"executor.run_sentiment",
            "extract_entities": "executor.run_ner",
            "tokenize":         "executor.run_tokenizer",
            "summarize":        "executor.run_summarizer",
        }
        return routes.get(intent, "handler.default")
