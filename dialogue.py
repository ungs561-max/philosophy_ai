import hashlib
import json
import re
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent
PROFILES = json.loads((ROOT / "profiles.json").read_text(encoding="utf-8-sig"))
MODES = ("counsel", "study")
POSES = ("background", "idle", "listening", "thinking", "speaking")
SECRET_NAMES = {
    "epictetus": ("DIFY_COUNSEL_KEY", "DIFY_STUDY_KEY"),
    "laozi": ("DIFY_LAOZI_COUNSEL_KEY", "DIFY_LAOZI_STUDY_KEY"),
    "smith": ("DIFY_SMITH_COUNSEL_KEY", "DIFY_SMITH_STUDY_KEY"),
    "camus": ("DIFY_CAMUS_COUNSEL_KEY", "DIFY_CAMUS_STUDY_KEY"),
}
ENDPOINT = "https://api.dify.ai/v1/chat-messages"
UUID = re.compile(r"[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}", re.I)


def picture_paths(profile):
    return {
        pose: ROOT / "static" / profile["folder"] / f"{image}.png"
        for pose, image in zip(POSES, profile["images"], strict=True)
    }


def read_quotes():
    content = (ROOT / "quotes.txt").read_text(encoding="utf-8-sig")
    for block in re.split(r"^\s*-\s*명언\s*:\s*", content, flags=re.M)[1:]:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        fields = {}
        for line in lines[1:-1]:
            match = re.fullmatch(r"-?\s*(성찰 질문|배정 철학자)\s*:\s*(.+)", line)
            if match:
                key, value = match.groups()
                fields[key] = value.strip()
        if len(lines) >= 3 and fields.get("성찰 질문"):
            quote = lines[0].strip('"“”')
            author = lines[-1]
            owner = fields.get("배정 철학자", author)
            card_id = hashlib.sha256(f"{author}\0{quote}".encode()).hexdigest()[:24]
            yield owner, card_id, dict(id=card_id, quote=quote, question=fields["성찰 질문"], philosopher=author)


quotes_by_name = {profile["name"]: {} for profile in PROFILES.values()}
for owner, card_id, card in read_quotes():
    if owner in quotes_by_name:
        quotes_by_name[owner][card_id] = card
QUOTES = {slug: quotes_by_name[profile["name"]] for slug, profile in PROFILES.items()}


def daily_cards():
    today = datetime.now(ZoneInfo("Asia/Seoul")).date().isoformat()
    index = int(hashlib.sha256(today.encode()).hexdigest(), 16)
    result = {}
    for slug, profile in PROFILES.items():
        concept = (profile["concept"], profile["nextConcept"])[index % 2]
        result[slug] = {
            "study": dict(zip(("term", "explanation", "philosopher", "topic"), concept)),
        }
    return result


def card_prompt(card, mode):
    if mode == "counsel":
        return (
            f"{card['philosopher']}의 명언을 바탕으로 '{card['question']}'에 대해 상담하고 싶어요.",
            "다음 명언을 시작점으로 철학 상담을 해 주세요. "
            "성찰 질문에 AI가 대신 답하지 말고, 사용자의 경험을 묻는 짧고 자연스러운 질문으로 대화를 시작해 주세요.\n\n"
            f"철학자: {card['philosopher']}\n명언: {card['quote']}\n성찰 질문: {card['question']}",
        )
    return (
        f"오늘의 철학 개념 '{card['term']}'을 공부하고 싶어요.",
        f"'{card['topic']}' 개념을 처음 공부하는 대학생에게 알기 쉽게 설명해 주세요. "
        "먼저 개념을 간단히 정의하고, 관련 철학적 배경과 현실적인 예시를 설명한 뒤 "
        "이해도를 확인할 질문을 하나 제시해 주세요. "
        "다음 카드 문장은 원전 직인용이 아닐 수 있는 학습용 요약이므로 정확한 원문인 것처럼 소개하지 마세요.\n\n"
        f"오늘의 개념: {card['term']}\n관련 철학자: {card['philosopher']}\n핵심 요약: {card['explanation']}",
    )


class DialogueError(Exception):
    pass


def run_dialogue(payload, api_key, card, publish):
    slug, mode = payload["id"], payload["mode"]
    display, query = card_prompt(card, mode) if payload["fromCard"] else (payload["text"], payload["text"])
    if payload["test"]:
        time.sleep(0.82)
        answer = PROFILES[slug]["demo"]
        if mode == "study":
            answer = f"{card['term']}\n\n{card['explanation']}\n\n{answer}"
        publish(display=display, answer=answer, conversationId="", done=True)
        return
    if not api_key:
        raise DialogueError("이 철학자의 대화 모드는 연결 준비 중입니다.")

    conversation_id = "" if payload["fromCard"] else payload["conversationId"]
    request = dict(inputs={}, query=query, response_mode="streaming",
                   conversation_id=conversation_id, user=payload["user"])
    deadline = time.monotonic() + 120
    try:
        with requests.post(ENDPOINT, json=request, stream=True,
                           headers={"Authorization": f"Bearer {api_key}"}, timeout=(10, 30)) as response:
            if not response.ok:
                if response.status_code == 429:
                    raise DialogueError("AI 모델 사용량 한도를 확인해 주세요.")
                raise DialogueError(f"Dify API 오류 ({response.status_code}). 연결 설정을 확인해 주세요.")
            if "text/event-stream" not in response.headers.get("Content-Type", ""):
                raise DialogueError("Dify 응답을 읽을 수 없습니다.")
            answer = ""
            for line in response.iter_lines(chunk_size=128):
                if time.monotonic() > deadline:
                    raise DialogueError("답변을 기다리는 시간이 초과되었습니다.")
                if not line.startswith(b"data:"):
                    continue
                event = json.loads(line[5:])
                kind = event.get("event")
                if kind == "error":
                    if "quota" in str(event.get("message", "")).lower():
                        raise DialogueError("AI 모델 사용량 한도를 확인해 주세요.")
                    raise DialogueError("Dify가 답변을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.")
                if kind in ("message", "agent_message", "message_replace", "message_end"):
                    candidate = event.get("conversation_id")
                    if isinstance(candidate, str) and UUID.fullmatch(candidate):
                        conversation_id = candidate
                if kind == "message_end" and answer.strip():
                    publish(display=display, answer=answer, conversationId=conversation_id, done=True)
                    return
                chunk = event.get("answer")
                if kind in ("message", "agent_message", "message_replace") and isinstance(chunk, str):
                    answer = chunk if kind == "message_replace" else answer + chunk
                    publish(display=display, answer=answer, conversationId=conversation_id)
    except requests.RequestException as error:
        raise DialogueError("Dify 서버에 연결할 수 없습니다. 잠시 후 다시 시도해 주세요.") from error
    except (ValueError, AttributeError) as error:
        raise DialogueError("Dify 응답을 읽을 수 없습니다.") from error
    raise DialogueError("답변을 모두 받기 전에 연결이 종료되었습니다.")
