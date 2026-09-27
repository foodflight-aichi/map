import os
import tweepy


def main():
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_KEY_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )

    text = "テスト投稿です。地域たすけあいマップの自動投稿の動作確認をしています。"
    response = client.create_tweet(text=text)
    print("投稿に成功しました:", response.data)


if __name__ == "__main__":
    main()
