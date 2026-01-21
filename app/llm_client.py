import json
import logging

from dotenv import load_dotenv
from openai import OpenAI

from app.prompts import ANALYZE_REVIEW_PROMPT
from app.schema import ReviewAnalysis

load_dotenv()
client = OpenAI()
logger = logging.getLogger(__name__)


def analyze_single_review(payload: dict) -> ReviewAnalysis:
    prompt = ANALYZE_REVIEW_PROMPT.format(**payload)

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You analyze app reviews. Return only valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=300,
    )

    content = response.choices[0].message.content.strip()

    # Remove markdown if present
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()

    # Parse JSON
    try:
        data = json.loads(content)
        return ReviewAnalysis(**data)
    except Exception as e:
        # Fallback if parsing fails
        logger.warning(f"Failed to parse LLM response for {payload.get('review_id')}: {e}")
        return ReviewAnalysis(
            review_id=payload["review_id"],
            category="other",
            urgency="medium",
            summary="Analysis failed",
            tags=[],
        )


if __name__ == "__main__":
    # Test
    test = {
        "review_id": "test_1",
        "review_text": "App keeps crashing on startup",
        "rating": 1,
        "thumbs_up": 0,
    }

    result = analyze_single_review(test)
    print(result.model_dump_json(indent=2))
