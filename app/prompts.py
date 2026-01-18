ANALYZE_REVIEW_PROMPT = """
You are an expert product analyst for mobile apps.

Analyze the following app review and return ONLY a valid JSON object.
Do NOT include markdown, explanations, or extra text.

Review context:
- Review ID: {review_id}
- Review Text: "{review_text}"
- Rating: {rating}/5
- Thumbs Up: {thumbs_up}

Return a JSON object with EXACTLY these fields:
{{
  "review_id": "{review_id}",
  "category": "bug|payment|ads|performance|feature_request|praise|complaint|other",
  "urgency": "low|medium|high",
  "summary": "one concise sentence",
  "tags": ["tag1", "tag2"]
}}

Category rules (apply in this priority order):
1. bug → crashes, errors, broken or unusable features
2. payment → payment failures, refunds, pricing issues
3. ads → intrusive or excessive ads
4. performance → slow, lag, freeze, battery drain
5. feature_request → requests for new features or improvements
6. praise → positive feedback or thanks
7. complaint → negative feedback without a specific technical issue
8. other → none of the above

Urgency rules:
- high → app unusable, crashes, payment failures, data loss
- medium → major annoyance, repeated issues, poor experience
- low → minor issues, suggestions, praise

Additional urgency signals:
- Rating ≤ 2 and Thumbs Up ≥ 10 → urgency must be at least "medium"
- Rating ≤ 2 and Thumbs Up ≥ 50 → urgency must be "high"

Tag rules:
- Use at most 5 tags
- Lowercase only
- Use underscores instead of spaces
- Tags must describe concrete issues or topics
- Avoid generic tags like "app", "issue", "problem"

IMPORTANT:
- Return ONLY valid JSON
- Do NOT omit any field
- Do NOT add extra keys
"""
