import os
import json
import csv
import random
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# ---------- Setup ----------
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
# BUG FIX: Valid model name required to run
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
        }
    }
]

# ---------- Tool Implementation ----------
def generate_quiz(topic: str, grade_level: str, num_questions: int, question_type: str = "mix", language: str = "ru") -> str:
    system = "You are a strict quiz generator. Return ONLY valid JSON."
    user = f"""
Create a quiz.
topic: {topic} | grade_level: {grade_level} | num_questions: {num_questions} | question_type: {question_type} | language: {language}

JSON format:
{{
  "topic": "...",
  "grade_level": "...",
  "items": [
    {{ "id": 1, "q": "...", "type": "mcq|short", "options": ["A","B","C","D"], "answer": "..." }}
  ]
}}
""".strip()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.2,
        response_format={"type": "json_object"}
    )
    return response.choices[0].message.content

AVAILABLE = {"generate_quiz": generate_quiz}
SYSTEM = "Ты ассистент учителя. Если пользователь просит квиз — вызывай generate_quiz."

# ---------- Added Logic for Requirements ----------

def run_quiz_game(quiz_json: str, seed: int):
    """Handles the interactive quiz, saving to quiz.json and report.csv"""
    data = json.loads(quiz_json)
    
    # Requirement: Save structure to quiz.json
    with open("quiz.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    random.seed(seed)
    score = 0
    total = len(data["items"])
    
    print(f"\n--- ТЕМА: {data['topic']} (Класс: {data['grade_level']}) ---")
    
    for item in data["items"]:
        print(f"\nВопрос: {item['q']}")
        
        if item["type"] == "mcq" and "options" in item:
            # Requirement: Predictable shuffling based on seed
            opts = list(item["options"])
            random.shuffle(opts)
            for i, opt in enumerate(opts, 1):
                print(f"{i}. {opt}")
            
            user_ans = input("Ваш ответ (текст или номер): ").strip()
            # Simple check logic
            is_correct = (user_ans.lower() == item["answer"].lower()) or \
                         (user_ans.isdigit() and int(user_ans) <= len(opts) and opts[int(user_ans)-1] == item["answer"])
        else:
            user_ans = input("Ваш ответ: ").strip()
            is_correct = user_ans.lower() == item["answer"].lower()

        if is_correct:
            print("✅ Правильно!")
            score += 1
        else:
            print(f"❌ Ошибка. Правильный ответ: {item['answer']}")

    # Requirement: Save results to report.csv
    print(f"\nВаш результат: {score}/{total}")
    file_exists = os.path.isfile("report.csv")
    with open("report.csv", "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["Date", "Topic", "Score", "Total", "Seed"])
        writer.writerow([datetime.now().strftime("%Y-%m-%d %H:%M"), data['topic'], score, total, seed])

def ask(user_text: str) -> str:
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user_text}]
    response = client.chat.completions.create(
        model=MODEL, messages=messages, functions=FUNCTIONS, function_call="auto"
    )
    msg = response.choices[0].message

    if not msg.function_call:
        return msg.content or ""

    fn_name = msg.function_call.name
    args = json.loads(msg.function_call.arguments)
    
    if fn_name == "generate_quiz":
        # Ask for seed before starting
        try:
            seed_input = int(input("Введите seed для перемешивания (число): ") or 42)
        except ValueError:
            seed_input = 42
            
        quiz_data = generate_quiz(**args)
        run_quiz_game(quiz_data, seed_input)
        return "Викторина завершена и сохранена."
    
    return "Инструмент не найден."

if __name__ == "__main__":
    print('Пример: "Сделай квиз по истории на 3 вопроса для 7-9"')
    try:
        while True:
            q = input("> ").strip()
            if q:
                print(ask(q))
    except KeyboardInterrupt:
        print("\nПока!")