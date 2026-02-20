"""Claude Code Release Radar のメインエントリーポイント。"""

import argparse
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

from src.classifier import classify_release
from src.github_client import get_new_releases, get_release_body, get_release_by_tag, get_release_version
from src.notifier import format_dry_run, notify
from src.state import get_last_version, save_last_version

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Claude Code Release Radar")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Slack 通知を送信せず標準出力に結果を表示する",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="特定バージョンのみを処理する（例: 1.0.23）",
    )
    args = parser.parse_args()

    # 特定バージョン指定時はそのリリースのみ処理
    if args.version:
        release = get_release_by_tag(args.version)
        if not release:
            logger.info("Release %s not found on GitHub", args.version)
            return
        new_releases = [release]
    else:
        # 1. 最後に処理したバージョンを取得
        last_version = get_last_version()
        logger.info("Last processed version: %s", last_version or "(none)")

        # 2. 新しいリリースを取得
        new_releases = get_new_releases(last_version)

    if not new_releases:
        logger.info("No new releases found since last check")
        return

    logger.info("Processing %d new release(s)", len(new_releases))

    # 3. 各リリースを処理
    latest_version = None
    for release in new_releases:
        version = get_release_version(release)
        body = get_release_body(release)
        logger.info("Processing release %s", version)

        # 分類・要約
        items = classify_release(body)

        if args.dry_run:
            print(format_dry_run(version, items))
            print()
        else:
            # 4. 通知送信（該当項目がある場合のみ）
            notify(version, items)

        latest_version = version

    # 5. 最新の処理済みバージョンで状態を更新
    if latest_version and not args.dry_run:
        save_last_version(latest_version)
        logger.info("Updated last processed version to %s", latest_version)

    logger.info("Done")


if __name__ == "__main__":
    main()
