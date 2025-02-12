import feedparser
import pandas as pd
import re
from datetime import datetime
import pytz
import json
import requests
from datetime import datetime, timedelta

# RSSフィード
FEEDS = {
    "CoinDesk Japan": {
        "url": "https://www.coindeskjapan.com/feed/",
        "category": "major",
    },
    "Cointelegraph JP": {
        "url": "https://jp.cointelegraph.com/rss",
        "category": "major",
    },
    "CoinPost": {"url": "https://coinpost.jp/?feed=rss2", "category": "major"},
    "CRYPTO TIMES": {"url": "https://crypto-times.jp/feed/", "category": "major"},
}


class CoinKeywordsManager:
    def __init__(self):
        self.keywords = set(
            [
                # フォールバック用の基本的なコインキーワード
                "BTC",
                "ETH",
                "XRP",
                "DOGE",
                "SHIB",
                "ビットコイン",
                "イーサリアム",
            ]
        )
        self.last_update = None
        self.update_interval = timedelta(hours=24)  # 更新間隔を24時間に設定

    def fetch_top_coins(self):
        """CoinGecko APIから上位コインの情報を取得"""
        try:
            response = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": 50,
                    "sparkline": False,
                },
                timeout=10,
            )
            response.raise_for_status()
            coins = response.json()

            new_keywords = set()
            for coin in coins:
                new_keywords.add(coin["symbol"].upper())
                new_keywords.add(coin["name"].lower())

            return new_keywords
        except Exception as e:
            print(f"Error fetching top coins: {e}")
            return None

    def update_if_needed(self):
        """必要な場合にキーワードリストを更新"""
        now = datetime.now()
        if self.last_update is None or now - self.last_update > self.update_interval:
            print("Updating coin keywords...")
            new_keywords = self.fetch_top_coins()
            if new_keywords:
                self.keywords.update(new_keywords)
                self.last_update = now
                print(f"Updated keywords. Total keywords: {len(self.keywords)}")
            else:
                print("Using existing keywords due to fetch failure")

    def get_keywords(self):
        """現在のキーワードリストを取得"""
        self.update_if_needed()

        return list(self.keywords)


# グローバルなインスタンスを作成
coin_keywords_manager = CoinKeywordsManager()

# カテゴリー設定
CATEGORIES = {
    "trending_coin": [
        # 既存の新規コイン関連
        "プレセール",
        "新規上場",
        "IDO",
        "IEO",
        "エアドロップ",
        "ミームコイン",
        "初期投資",
        "新規コイン",
        "新規トークン",
        # 既存の価格変動関連
        "急騰",
        "暴騰",
        "高騰",
        "上昇",
        "急落",
        "暴落",
        # 既存の取引所関連
        "上場",
        "リスティング",
        "取扱開始",
        # 既存の話題性
        "注目",
        "話題",
        "トレンド",
        "人気",
        "バイラル",
        # 既存のプロジェクト動向
        "エコシステム",
        "新規参入",
        "新プロジェクト",
        # 【追加】将来性・期待に関する表現
        "期待",
        "有望",
        "将来性",
        "成長",
        "ポテンシャル",
        # 【追加】具体的な数値表現
        "倍",
        "％",
        "最高値",
        # 【追加】投資機会のタイミング
        "底値",
        "買い場",
        "仕込み時",
        # 【追加】機関投資家・大口関連
        "ホエール",
        "機関投資家",
        "大量保有",
        # 【追加】プロジェクトの進展
        "アップデート",
        "開発進展",
        "提携",
        "パートナーシップ",
    ],
    # 既存の他のカテゴリーはそのまま維持
    "market_analysis": [
        "市場分析",
        "テクニカル分析",
        "価格分析",
        "相場動向",
        "マーケット概況",
        "値動き",
    ],
    "project_info": [
        "トークノミクス",
        "ロードマップ",
        "チーム紹介",
        "開発状況",
        "ホワイトペーパー",
        "技術概要",
    ],
}


def categorize_article(title, content):
    """記事のカテゴリーを判定"""
    text = f"{title} {content}".lower()

    # 動的に更新されるコインキーワードを使用
    if any(coin.lower() in text for coin in coin_keywords_manager.get_keywords()):
        return "trending_coin"

    # 既存のカテゴリーチェック
    for category, keywords in CATEGORIES.items():
        if any(keyword in text for keyword in keywords):
            return category

    return "general"


def fetch_news():
    """ニュース取得処理"""
    news_items = []
    jst = pytz.timezone("Asia/Tokyo")

    for source, info in FEEDS.items():
        try:
            print(f"Fetching from {source}...")
            feed = feedparser.parse(info["url"])

            for entry in feed.entries[:10]:
                content = re.sub(r"<[^>]+>", "", entry.description)
                article_category = categorize_article(entry.title, content)
                published = datetime.strptime(
                    entry.published, "%a, %d %b %Y %H:%M:%S %z"
                )
                published_jst = published.astimezone(jst)

                news_items.append(
                    {
                        "source": source,
                        "source_category": info["category"],
                        "article_category": article_category,
                        "title": entry.title,
                        "content_summary": content[:200] + "...",
                        "url": entry.link,
                        "published": published_jst.strftime("%Y-%m-%d %H:%M:%S"),
                        "fetch_time": datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S"),
                    }
                )

        except Exception as e:
            print(f"Error fetching from {source}: {e}")

    return pd.DataFrame(news_items)


def save_for_astro(df):
    """AstroサイトのためのJSONファイルを生成"""
    # 日付フォーマットの変換
    df["published"] = pd.to_datetime(df["published"]).dt.strftime("%Y-%m-%d %H:%M:%S")

    # カテゴリー別の記事数を集計
    category_counts = df["article_category"].value_counts().to_dict()

    # メディア別の記事数を集計
    source_counts = df["source"].value_counts().to_dict()

    # 出力データの準備
    output_data = {
        "articles": df.to_dict("records"),
        "categories": category_counts,
        "sources": source_counts,
        "lastUpdated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    # JSONファイルとして保存
    with open("src/data/crypto_news.json", "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)


def main():
    # コインキーワードの更新をチェック
    print("Checking for coin keywords update...")
    coin_keywords_manager.update_if_needed()

    # 新規ニュースの取得
    print("Fetching new articles...")
    df = fetch_news()

    print("Generating JSON for Astro site...")
    save_for_astro(df)


if __name__ == "__main__":
    main()
