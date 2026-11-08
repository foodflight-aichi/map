import json
import os
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAP_URL = "https://foodflight-aichi.github.io/map/"

# URL入りの投稿は料金が高い(1件約0.2ドル)ため、1日2回だけにする。
# GitHub Actionsは数十分遅れることがあるので、時刻ではなく「時間帯」で判定する。
#   朝: 07:30の実行 → 7:00〜8:59 / 夜: 19:00の実行 → 19:00〜20:29
# (9:00の実行は9:00以降、20:30の実行は20:30以降に始まるので、混ざらない)
URL_WINDOWS_JST = [(7 * 60, 9 * 60), (19 * 60, 20 * 60 + 30)]

DATA_FILES = {
    "kodomo_shokudo": "data/spots.json",
    "food_bank": "data/foodbanks.json",
    "food_drive": "data/fooddrives.json",
    "takidashi": "data/soupkitchens.json",
}

CATEGORY_LABEL = {
    "kodomo_shokudo": "こども食堂",
    "food_bank": "フードバンク",
    "food_drive": "フードドライブBOX",
    "takidashi": "炊き出し",
}

LOG_PATH = Path("data/posted_log.json")

URL_LIKE = re.compile(
    r"https?://\S+|www\.\S+|\b[\w-]+(?:\.[\w-]+)*\.(?:com|jp|net|org|io|info|co)\b\S*",
    re.IGNORECASE,
)


def current_minutes_jst():
    """JSTの現在時刻を「0時からの分」で返す。テスト用に JST_TIME_OVERRIDE=HH:MM で上書きできる。"""
    override = os.environ.get("JST_TIME_OVERRIDE")
    if override:
        h, m = override.split(":")
        return int(h) * 60 + int(m)
    now = datetime.now(timezone(timedelta(hours=9)))
    return now.hour * 60 + now.minute


def is_url_slot(minutes):
    return any(start <= minutes < end for start, end in URL_WINDOWS_JST)


def load_all_spots():
    all_spots = []
    for category, path in DATA_FILES.items():
        p = Path(path)
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            items = json.load(f)
        for item in items:
            item = dict(item)
            item["_category"] = category
            item["_key"] = f"{category}:{item.get('id')}"
            all_spots.append(item)
    return all_spots


def load_posted_log():
    if not LOG_PATH.exists():
        return []
    with LOG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def save_posted_log(log):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def pick_unposted_spot(all_spots, posted_keys):
    candidates = [s for s in all_spots if s["_key"] not in posted_keys]
    if not candidates:
        candidates = all_spots
    return random.choice(candidates) if candidates else None


def link_lines(with_url, lead):
    """URL入りの時は地図のURL、URLなしの時はプロフィール誘導の1行を返す。"""
    if with_url:
        return [lead, MAP_URL]
    return ["▶地図はプロフィールのリンクから"]


def strip_urls(text):
    """URLなし投稿にURLらしき文字列が混ざっていたら取り除く(高い料金区分になるため)。"""
    cleaned = URL_LIKE.sub("", text)
    return re.sub(r"[ \t]+\n", "\n", cleaned).strip()


def build_spot_pickup_text(spot, with_url):
    label = CATEGORY_LABEL.get(spot["_category"], "拠点")
    name = spot.get("name", "")
    address = spot.get("address", spot.get("city", ""))
    schedule = spot.get("schedule", "")
    conditions = spot.get("conditions", "")

    lines = ["【拠点ピックアップ】", f"{address}の「{name}」さんをご紹介📍"]
    if schedule:
        lines.append(f"開催:{schedule}")
    if conditions:
        lines.append(conditions)
    lines.append("")
    lines.extend(link_lines(with_url, "▶詳細は地図で"))
    lines.append("")
    lines.append(f"#{label} #愛知")
    return "\n".join(lines)


def build_stats_text(all_spots, with_url):
    total = len(all_spots)
    lines = [
        f"【愛知県内{total}拠点を地図に掲載📍】",
        "こども食堂・フードバンク・炊き出し・フードドライブBOXを1つのマップで検索できます。",
        "利用は無料、誰でも使えます。",
        "",
    ]
    lines.extend(link_lines(with_url, "▶地図はこちら"))
    lines.append("")
    lines.append("#こども食堂 #フードバンク #愛知 #地域たすけあいマップ")
    return "\n".join(lines)


def build_recruit_text():
    lines = [
        "【掲載団体さま募集中】",
        "こども食堂・フードバンク・炊き出し・フードドライブを運営されている方、地図への掲載は無料です📍",
        "",
        "情報を届けたい方に、ちゃんと届く場所を作っています。",
        "掲載希望・情報提供はDMまたはリプライでお気軽にどうぞ。",
        "",
        "#こども食堂 #フードバンク募集 #愛知",
    ]
    return "\n".join(lines)


def build_intro_text(with_url):
    lines = [
        "愛知県内のこども食堂・フードバンク・炊き出し・フードドライブBOXを1つの地図で検索できるサービスです📍",
        "",
        "利用は無料、誰でも使えます。",
        "運営:フードフライト愛知",
        "",
    ]
    lines.extend(link_lines(with_url, "▶地図はこちら"))
    return "\n".join(lines)


def choose_genre(with_url):
    genres = ["spot_pickup"] * 6 + ["stats", "recruit", "intro"]
    if with_url:
        # URL入りの枠(高い)は、URLを使わない「団体募集」で無駄にしない
        genres = [g for g in genres if g != "recruit"]
    return random.choice(genres)


def build_post(genre, all_spots, posted_keys, with_url):
    """(本文, 投稿済みに記録するキー or None) を返す。"""
    if genre == "spot_pickup" and all_spots:
        spot = pick_unposted_spot(all_spots, posted_keys)
        return build_spot_pickup_text(spot, with_url), spot["_key"]
    if genre == "stats":
        return build_stats_text(all_spots, with_url), None
    if genre == "recruit":
        return build_recruit_text(), None
    return build_intro_text(with_url), None


def main():
    all_spots = load_all_spots()
    posted_log = load_posted_log()
    posted_keys = set(posted_log)

    minutes = current_minutes_jst()
    with_url = is_url_slot(minutes)

    genre = choose_genre(with_url)
    text, log_key = build_post(genre, all_spots, posted_keys, with_url)
    if not with_url:
        text = strip_urls(text)

    print(f"JST {minutes // 60:02d}:{minutes % 60:02d} / URL入り: {with_url} / ジャンル: {genre}")

    if os.environ.get("DRY_RUN") == "1":
        print("--- DRY RUN(投稿しません) ---")
        print(text)
        return

    import tweepy

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_KEY_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )

    try:
        response = client.create_tweet(text=text)
    except tweepy.Forbidden as e:
        # 同じ文面の連投(重複)などで拒否された時は、拠点ピックアップに切り替えて1回だけ再試行
        print("拒否されました。拠点ピックアップに切り替えて再試行します:", e)
        text, log_key = build_post("spot_pickup", all_spots, posted_keys, with_url)
        if not with_url:
            text = strip_urls(text)
        response = client.create_tweet(text=text)

    print("投稿しました:")
    print(text)
    print("response:", response.data)

    if log_key:
        posted_log.append(log_key)
    save_posted_log(posted_log)


if __name__ == "__main__":
    main()
