"""Reply keyboard at the bottom of the chat, with a back stack for each screen."""

from apps.telegram.models import TelegramDraft

NAV_KEYS = ("_stack", "_here", "_keys")
BACK = "رجوع"
# Reopening these starts a flow again, so Back from the first screen returns home.
FLOW_STARTS = {"nw", "mc"}
EXPLICIT_BACK = {"gp:0"}


def keep_nav(previous, payload):
    payload = dict(payload or {})
    previous = previous or {}
    for key in NAV_KEYS:
        if key in previous and key not in payload:
            payload[key] = previous[key]
    return payload


def _draft(chat_id):
    draft, _created = TelegramDraft.objects.get_or_create(
        chat_id=str(chat_id), defaults={"step": "", "payload": {}},
    )
    return draft


def reset_place(chat_id):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None:
        return
    payload = dict(draft.payload or {})
    payload["_stack"] = []
    payload["_here"] = None
    draft.payload = payload
    draft.save(update_fields=["payload", "updated_at"])


def track(chat_id, data):
    """Remember this screen so رجوع can reopen the previous one."""
    draft = _draft(chat_id)
    payload = dict(draft.payload or {})
    stack = list(payload.get("_stack") or [])
    here = payload.get("_here")
    if data == "bk" or data in EXPLICIT_BACK:
        if data == "bk":
            data = stack.pop() if stack else "mn"
            if data in FLOW_STARTS:
                data = "mn"
        if data == "mn":
            stack = []
            here = None
        else:
            here = data
    elif data == "mn":
        stack = []
        here = None
    else:
        if here and here != data:
            stack.append(here)
            stack = stack[-12:]
        here = data
    payload["_stack"] = stack
    payload["_here"] = here
    draft.payload = payload
    draft.save(update_fields=["payload", "updated_at"])
    return data


def _key_button(button):
    item = {"text": button["text"]}
    if button.get("style") in {"danger", "primary", "success"}:
        item["style"] = button["style"]
    if button.get("request_location"):
        item["request_location"] = True
    if button.get("web_app"):
        item["web_app"] = button["web_app"]
    return item


def attach_keyboard(chat_id, markup):
    """Turn an inline keyboard into the persistent reply keyboard and remember each label."""
    if not markup or "inline_keyboard" not in markup:
        return markup
    rows = [list(row) for row in markup["inline_keyboard"]]
    labels = [button["text"] for row in rows for button in row]
    is_root = "تقديم شكوى" in labels
    if not is_root and BACK not in labels:
        rows.append([{"text": BACK, "callback_data": "bk"}])
    mapping = {
        button["text"]: button["callback_data"]
        for row in rows for button in row if button.get("callback_data")
    }
    draft = _draft(chat_id)
    payload = dict(draft.payload or {})
    payload["_keys"] = mapping
    draft.payload = payload
    draft.save(update_fields=["payload", "updated_at"])
    return {
        "keyboard": [[_key_button(button) for button in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def bound_action(chat_id, text):
    draft = TelegramDraft.objects.filter(chat_id=str(chat_id)).first()
    if draft is None:
        return None
    return (draft.payload or {}).get("_keys", {}).get(text)


def as_reply_markup(markup):
    if not markup or "keyboard" in markup or "inline_keyboard" not in markup:
        return markup
    return {
        "keyboard": [[_key_button(button) for button in row] for row in markup["inline_keyboard"]],
        "resize_keyboard": True,
        "is_persistent": True,
    }
