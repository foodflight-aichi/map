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

JST = timezone(timedelta(hours=9))

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
            
            # 重複チェック
            if url in existing_urls:
                continue
            
            # 愛知県関連かチェック
            full_text = title + summary
            if not is_aichi_related(full_text):
                continue
            
            # 支援活動関連かチェック
            if not is_support_related(full_text):
                continue
            
            candidate = {
                "id": f"cand_{len(existing) + len(new_candidates) + 1}",
                "title": title,
                "url": url,
                "source": source,
                "published": published,
                "summary": summary[:200],
                "keyword": keyword,
                "status": "未確認",  # 未確認 / 承認 / 却下
                "found_at": datetime.now(JST).strftime("%Y-%m-%d"),
            }
            
            new_candidates.append(candidate)
            existing_urls.add(url)
            print(f"  新規候補: {title[:40]}...")
    
    # 既存 + 新規を保存（最新300件まで）
    all_candidates = new_candidates + existing
    all_candidates = all_candidates[:300]
    
    os.makedirs("data", exist_ok=True)
    with open("data/candidates.json", "w", encoding="utf-8") as f:
        json.dump(all_candidates, f, ensure_ascii=False, indent=2)
    
    print(f"完了: 新規{len(new_candidates)}件 / 合計{len(all_candidates)}件")

if __name__ == "__main__":
    main()

