import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Setup ----------
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# FIXED: Changed to a valid model name
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ---------- Function Schema ----------
FUNCTIONS = [
    {
        "name": "generate_quiz",
        "description": "Generate a school quiz in JSON format",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string"},
                "grade_level": {
                    "type": "string",
                    "enum": ["K-3", "4-6", "7-9", "10-12"]
                },
                "num_questions": {
                    "type": "integer",
                    "minimum": 3,
                    "maximum": 20
                },
                "question_type": {
                    "type": "string",
                    "enum": ["mcq", "short", "mix"],
                    "default": "mix"
                },
                "language": {
                    "type": "string",
                    "enum": ["ru", "en"],
                    "default": "ru"
                }
            },
            "required": ["topic", "grade_level", "num_questions"]
        },
        # REMOVED "strict": True here because it crashes the 'functions' parameter
    }
]

# ---------- Tool Implementation ----------
def generate_quiz(
    topic: str,
    grade_level: str,
    num_questions: int,
    question_type: str = "mix",
    language: str = "ru"
) -> str:
    system = "You are a strict quiz generator. Return ONLY valid JSON."
    user = f"""
Create a quiz.
topic: {topic}
grade_level: {grade_level}
num_questions: {num_questions}
question_type: {question_type}
language: {language}

JSON format:
{{
  "topic": "...",
  "grade_level": "...",
  "items": [
    {{
      "id": 1,
      "q": "...",
      "type": "mcq|short",
      "options": ["A","B","C","D"],
      "answer": "..."
    }}
  ],
  "answer_key": [
    {{"id": 1, "answer": "..."}}
  ]
}}
""".strip()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        temperature=0.2,
        response_format={"type": "json_object"}
    )

    return response.choices[0].message.content


AVAILABLE = {
    "generate_quiz": generate_quiz
}

SYSTEM = (
    "Ты ассистент учителя. "
    "Если пользователь просит квиз — вызывай generate_quiz. "
    "Если данных не хватает — задай уточняющий вопрос."
)


def ask(user_text: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_text}
    ]

    # This call now works because 'strict' was removed from FUNCTIONS above
    response = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        functions=FUNCTIONS,
        function_call="auto",
        temperature=0
    )

    msg = response.choices[0].message

    if not msg.function_call:
        return msg.content or ""

    fn_name = msg.function_call.name
    args = json.loads(msg.function_call.arguments)

    fn = AVAILABLE.get(fn_name)
    if not fn:
        return "Инструмент не найден."

    return fn(**args)


if __name__ == "__main__":
    print('Пример: "Сделай квиз по дробям для 4-6 на 5 вопросов"')

    try:
        while True:
            q = input("> ").strip()
            if q:
                print(ask(q))
    except KeyboardInterrupt:
        print("\nПока!")