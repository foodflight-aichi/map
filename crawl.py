"""
拠点情報自動巡回スクリプト
Google News RSSから愛知県内のこども食堂・フードバンク・炊き出し情報を収集し
data/candidates.jsonに保存する
"""

import feedparser
import json
import os
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import quote
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 日付フィルタ設定
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FETCH_MAX_AGE_DAYS = 30   # 取得時: この日数より古い記事は無視
KEEP_MAX_AGE_DAYS  = 90   # 保存時: この日数より古い記事はJSONから削除
MAX_CANDIDATES     = 300  # 保存件数の上限

# 検索キーワード
KEYWORDS = [
    "こども食堂 愛知",
    "子ども食堂 愛知",
    "フードバンク 愛知",
    "炊き出し 愛知",
    "フードドライブ 愛知",
    "こども食堂 名古屋",
    "フードパントリー 愛知",
]

# 愛知県内の市区町村（フィルタリング用）
AICHI_CITIES = [
    "名古屋", "豊田", "岡崎", "一宮", "豊橋", "春日井", "豊川", "津島",
    "碧南", "刈谷", "安城", "西尾", "蒲郡", "犬山", "常滑", "江南",
    "小牧", "稲沢", "新城", "東海", "大府", "知多", "知立", "尾張旭",
    "高浜", "岩倉", "豊明", "日進", "田原", "愛西", "清須", "北名古屋",
    "弥富", "みよし", "あま", "長久手", "愛知"
]

def fetch_google_news(keyword):
    """Google NewsのRSSから記事を取得"""
    url = f"https://news.google.com/rss/search?q={quote(keyword)}&hl=ja&gl=JP&ceid=JP:ja"
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print(f"エラー: {keyword} - {e}")
        return []

def parse_published(published_str):
    """
    RSS の published 文字列 (RFC 2822) を datetime(JST) に変換。
    パース失敗時は None を返す。
    例: "Mon, 03 Jun 2024 08:30:00 GMT" → datetime(2024, 6, 3, 17, 30, tzinfo=JST)
    """
    if not published_str:
        return None
    try:
        dt = parsedate_to_datetime(published_str)
        return dt.astimezone(JST)
    except Exception:
        return None

def is_recent_entry(published_str, max_age_days):
    """記事が max_age_days 以内かどうか判定。日付不明は除外。"""
    dt = parse_published(published_str)
    if dt is None:
        return False  # 日付不明は除外（古い記事が混じるため）
    cutoff = datetime.now(JST) - timedelta(days=max_age_days)
    return dt >= cutoff

def is_aichi_related(text):
    """愛知県関連の記事かチェック"""
    return any(city in text for city in AICHI_CITIES)

def is_support_related(text):
    """支援活動関連の記事かチェック"""
    keywords = ["こども食堂", "子ども食堂", "フードバンク", "炊き出し",
                "フードドライブ", "フードパントリー", "食料支援", "食品寄付"]
    return any(kw in text for kw in keywords)

def load_existing_candidates():
    """既存の候補リストを読み込む"""
    path = "data/candidates.json"
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return []

def purge_old_candidates(candidates, max_age_days):
    """
    found_at が古すぎる記事を除外する（承認済みは残す）。
    candidates.json が古い記事で埋まるのを防ぐ。
    """
    cutoff = datetime.now(JST) - timedelta(days=max_age_days)
    kept, removed = [], []
    for c in candidates:
        # 承認済みは削除しない
        st = c.get("status", "未確認")
        if st == "承認":
            kept.append(c)
            continue
        # found_at で判定
        found_at_str = c.get("found_at", "")
        try:
            found_dt = datetime.strptime(found_at_str, "%Y-%m-%d").replace(tzinfo=JST)
            if found_dt >= cutoff:
                kept.append(c)
            else:
                removed.append(c)
        except ValueError:
            kept.append(c)  # パース失敗は残す
    if removed:
        print(f"  古い記事を除外: {len(removed)}件（{max_age_days}日超）")
    return kept

def main():
    print(f"巡回開始: {datetime.now(JST).strftime('%Y-%m-%d %H:%M')}")
    print(f"取得フィルタ: 直近{FETCH_MAX_AGE_DAYS}日以内の記事のみ")

    existing = load_existing_candidates()

    # ── 保存済みの古い記事を先に掃除 ──
    existing = purge_old_candidates(existing, KEEP_MAX_AGE_DAYS)

    existing_urls = {c["url"] for c in existing}

    new_candidates = []

    for keyword in KEYWORDS:
        print(f"検索中: {keyword}")
        entries = fetch_google_news(keyword)

        for entry in entries:
            url       = entry.get("link", "")
            title     = entry.get("title", "")
            summary   = entry.get("summary", "")
            published = entry.get("published", "")
            source    = entry.get("source", {}).get("title", "不明")

            # ── ① 日付フィルタ（古い記事を除外）──
            if not is_recent_entry(published, FETCH_MAX_AGE_DAYS):
                continue

            # ── ② 重複チェック ──
            if url in existing_urls:
                continue

            # ── ③ 愛知県関連かチェック ──
            full_text = title + summary
            if not is_aichi_related(full_text):
                continue

            # ── ④ 支援活動関連かチェック ──
            if not is_support_related(full_text):
                continue

            # published を "YYYY-MM-DD" 形式に整形して保存
            pub_dt = parse_published(published)
            pub_date_str = pub_dt.strftime("%Y-%m-%d") if pub_dt else ""

            candidate = {
                "id": f"cand_{len(existing) + len(new_candidates) + 1}",
                "title": title,
                "url": url,
                "source": source,
                "published": pub_date_str,       # 整形済み日付
                "published_raw": published,       # 元の文字列（デバッグ用）
                "summary": summary[:200],
                "keyword": keyword,
                "status": "未確認",
                "found_at": datetime.now(JST).strftime("%Y-%m-%d"),
            }

            new_candidates.append(candidate)
            existing_urls.add(url)
            print(f"  新規候補: [{pub_date_str}] {title[:40]}...")

    # 既存 + 新規を保存（上限件数まで）
    all_candidates = new_candidates + existing
    all_candidates = all_candidates[:MAX_CANDIDATES]

    os.makedirs("data", exist_ok=True)
    with open("data/candidates.json", "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, ensure_ascii=False, indent=2)

    print(f"完了: 新規{len(new_candidates)}件 / 合計{len(all_candidates)}件")

if __name__ == "__main__":
    main()
