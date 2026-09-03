

class PromptService:
    
    def build_prompt(self, request: list[str]) -> str:
        if request:
            formatted_chunks = "\n\n".join(
                f"[Chunk {i+1}]:\n{chunk}"
                for i, chunk in enumerate(request)
            )
        else:
            formatted_chunks = "Standard Legal Agreement Document context."

        prompt = f"""You are an expert AI contract reviewer. Analyze the following legal contract context carefully and provide a comprehensive analysis.

--- CONTEXT START ---
{formatted_chunks}
--- CONTEXT END ---

You MUST respond strictly with a single valid JSON object containing the following fields:
- "summary": A detailed summary string of the contract text.
- "risk_score": An integer from 0 (safest) to 100 (highest risk).
- "risk": A string enum, exactly one of "LOW", "MEDIUM", or "HIGH".
- "suggestions": A list of string recommendations/findings regarding clauses or risks.
- "confidence": A float between 0.0 and 1.0 indicating analysis confidence.

Return ONLY the JSON object."""
        return prompt

    