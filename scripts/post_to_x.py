import json
import os
import random
from pathlib import Path

import tweepy

MAP_URL = "https://foodflight-aichi.github.io/map/"

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


def build_spot_pickup_text(spot):
    label = CATEGORY_LABEL.get(spot["_category"], "拠点")
    name = spot.get("name", "")
    address = spot.get("address", spot.get("city", ""))
    schedule = spot.get("schedule", "")
    conditions = spot.get("conditions", "")

    lines = [f"【拠点ピックアップ】", f"{address}の「{name}」さんをご紹介📍"]
    if schedule:
        lines.append(f"開催:{schedule}")
    if conditions:
        lines.append(conditions)
    lines.append("")
    lines.append("▶詳細は地図で")
    lines.append(MAP_URL)
    lines.append("")
    lines.append(f"#{label} #愛知")
    return "\n".join(lines)


def build_stats_text(all_spots):
    total = len(all_spots)
    lines = [
        f"【愛知県内{total}拠点を地図に掲載📍】",
        "こども食堂・フードバンク・炊き出し・フードドライブBOXを1つのマップで検索できます。",
        "利用は無料、誰でも使えます。",
        "",
        "▶地図はこちら",
        MAP_URL,
        "",
        "#こども食堂 #フードバンク #愛知 #地域たすけあいマップ",
    ]
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


def build_intro_text():
    lines = [
        "愛知県内のこども食堂・フードバンク・炊き出し・フードドライブBOXを1つの地図で検索できるサービスです📍",
        "",
        "利用は無料、誰でも使えます。",
        "運営:フードフライト愛知",
        "",
        "▶地図はこちら",
        MAP_URL,
    ]
    return "\n".join(lines)


def choose_genre():
    genres = ["spot_pickup"] * 6 + ["stats", "recruit", "intro"]
    return random.choice(genres)


def main():
    all_spots = load_all_spots()
    posted_log = load_posted_log()
    posted_keys = set(posted_log)

    genre = choose_genre()

    if genre == "spot_pickup" and all_spots:
        spot = pick_unposted_spot(all_spots, posted_keys)
        text = build_spot_pickup_text(spot)
        posted_log.append(spot["_key"])
    elif genre == "stats":
        text = build_stats_text(all_spots)
    elif genre == "recruit":
        text = build_recruit_text()
    else:
        text = build_intro_text()

    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_KEY_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )

    response = client.create_tweet(text=text)
    print("投稿しました:")
    print(text)
    print("response:", response.data)

    save_posted_log(posted_log)


if __name__ == "__main__":
    main()
