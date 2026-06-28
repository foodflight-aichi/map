"""
拠点情報自動巡回スクリプト
Google News RSSから愛知県内のこども食堂・フードバンク・炊き出し情報を収集し
data/candidates.jsonに保存する
"""

import feedparser
import json
import os
from datetime import datetime, timezone, timedelta
from urllib.parse import quote

JST = timezone(timedelta(hours=9))

# 検索キーワード（より絞り込んだ）
KEYWORDS = [
    "こども食堂 開催 愛知",
    "子ども食堂 開催 愛知",
    "こども食堂 オープン 愛知",
    "フードバンク 受付 愛知",
    "フードバンク 配布 愛知",
    "炊き出し 開催 愛知",
    "炊き出し 名古屋",
    "フードドライブ 愛知",
    "フードパントリー 愛知",
    "こども食堂 名古屋 新規",
]

# 愛知県内の市区町村
AICHI_CITIES = [
    "名古屋", "豊田", "岡崎", "一宮", "豊橋", "春日井", "豊川", "津島",
    "碧南", "刈谷", "安城", "西尾", "蒲郡", "犬山", "常滑", "江南",
    "小牧", "稲沢", "新城", "東海", "大府", "知多", "知立", "尾張旭",
    "高浜", "岩倉", "豊明", "日進", "田原", "愛西", "清須", "北名古屋",
    "弥富", "みよし", "あま", "長久手", "愛知"
]

# 拠点関連キーワード（これが含まれている記事だけ採用）
SUPPORT_KEYWORDS = [
    "こども食堂", "子ども食堂", "フードバンク", "炊き出し",
    "フードドライブ", "フードパントリー", "食料支援", "食品寄付",
    "食堂", "居場所", "支援食", "無料食事"
]

# 拠点情報らしいキーワード（より関連性が高い記事を優先）
ACTIVITY_KEYWORDS = [
    "開催", "オープン", "募集", "参加", "受付", "配布", "無料",
    "新設", "開所", "スタート", "始まり", "毎月", "毎週"
]

# 除外キーワード（これが含まれていたら除外）
EXCLUDE_KEYWORDS = [
    "レシピ", "料理教室", "グルメ", "レストラン", "食べ歩き",
    "旅行", "観光", "ホテル", "居酒屋", "カフェ紹介"
]

def fetch_google_news(keyword):
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print(f"エラー: {keyword} - {e}")
        return []

def is_aichi_related(text):
    return any(city in text for city in AICHI_CITIES)

def is_support_related(text):
    return any(kw in text for kw in SUPPORT_KEYWORDS)

def has_activity_keyword(text):
    return any(kw in text for kw in ACTIVITY_KEYWORDS)

def has_exclude_keyword(text):
    return any(kw in text for kw in EXCLUDE_KEYWORDS)

def score_article(text):
    """記事の関連スコアを計算（高いほど関連性が高い）"""
    score = 0
    for kw in SUPPORT_KEYWORDS:
        if kw in text:
            score += 2
    for kw in ACTIVITY_KEYWORDS:
        if kw in text:
            score += 1
    for city in AICHI_CITIES:
        if city in text:
            score += 1
    return score

def load_existing_candidates():
    path = "data/candidates.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []

def main():
    print(f"巡回開始: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}")

    existing = load_existing_candidates()
    existing_urls = {c["url"] for c in existing}

    new_candidates = []

    for keyword in KEYWORDS:
        print(f"検索中: {keyword}")
        entries = fetch_google_news(keyword)

        for entry in entries:
            url = entry.get("link", "")
            title = entry.get("title", "")
            summary = entry.get("summary", "")
            published = entry.get("published", "")
            source = entry.get("source", {}).get("title", "不明")

            if url in existing_urls:
                continue

            full_text = title + " " + summary

            # 除外キーワードチェック
            if has_exclude_keyword(full_text):
                continue

            # 愛知県関連かチェック
            if not is_aichi_related(full_text):
                continue

            # 支援活動関連かチェック
            if not is_support_related(full_text):
                continue

            # 活動キーワードチェック（より関連性が高い記事を優先）
            if not has_activity_keyword(full_text):
                continue

            score = score_article(full_text)

            candidate = {
                "id": f"cand_{len(existing) + len(new_candidates) + 1}",
                "title": title,
                "url": url,
                "source": source,
                "published": published,
                "summary": summary[:200],
                "keyword": keyword,
                "score": score,
                "status": "未確認",
                "found_at": datetime.now(JST).strftime("%Y-%m-%d"),
            }

            new_candidates.append(candidate)
            existing_urls.add(url)
            print(f"  新規候補(スコア{score}): {title[:40]}...")

    # スコア順にソート
    new_candidates.sort(key=lambda x: x["score"], reverse=True)

    # 既存 + 新規を保存（最新300件まで）
    all_candidates = new_candidates + existing
    all_candidates = all_candidates[:300]

    os.makedirs("data", exist_ok=True)
    with open("data/candidates.json", "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, ensure_ascii=False, indent=2)

    print(f"完了: 新規{len(new_candidates)}件 / 合計{len(all_candidates)}件")

if __name__ == "__main__":
    main()
