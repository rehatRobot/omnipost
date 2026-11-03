# tests/test_tencent_content_stats.py
import unittest

from uploader.tencent_uploader.content_stats import (
    is_tencent_list_api_url,
    merge_intercepted_payloads,
    parse_tencent_item,
    parse_tencent_list_payload,
)


SAMPLE = {
    "errCode": 0,
    "errMsg": "",
    "data": {
        "list": [
            {
                "objectId": "old",
                "createTime": 1700000000,
                "status": 1,
                "readCount": 9,
                "likeCount": 1,
                "commentCount": 0,
                "forwardCount": 0,
                "favCount": 0,
                "desc": {
                    "description": "旧作品",
                    "media": [{"coverUrl": "https://example.com/a.jpg"}],
                },
            },
            {
                "objectId": "newest",
                "createTime": 1730000000,
                "status": 1,
                "readCount": 100,
                "likeCount": 10,
                "commentCount": 2,
                "forwardCount": 1,
                "favCount": 3,
                "objectDesc": {
                    "description": "最新",
                    "media": [{"coverUrl": "https://example.com/b.jpg"}],
                },
            },
            {
                "objectId": "mid",
                "createTime": 1720000000,
                "status": 1,
                "readCount": 50,
                "likeCount": 5,
                "commentCount": 1,
                "forwardCount": 0,
                "favCount": 1,
                "desc": {
                    "description": "中间",
                    "media": [{"coverUrl": "https://example.com/c.jpg"}],
                },
            },
        ]
    },
}


class TestTencentContentStats(unittest.TestCase):
    def test_url_hints(self):
        self.assertTrue(
            is_tencent_list_api_url(
                "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/post/post_list?_rid=1"
            )
        )
        self.assertTrue(
            is_tencent_list_api_url(
                "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin/statistic/post_list"
            )
        )
        self.assertTrue(
            is_tencent_list_api_url(
                "https://channels.weixin.qq.com/micro/content/cgi-bin/mmfinderassistant-bin/post/post_list?_rid=1"
            )
        )
        self.assertFalse(is_tencent_list_api_url("https://channels.weixin.qq.com/platform/post/list"))

    def test_parse_item(self):
        item = parse_tencent_item(SAMPLE["data"]["list"][1])
        self.assertEqual(item["item_id"], "newest")
        self.assertEqual(item["title"], "最新")
        self.assertEqual(item["play_count"], 100)
        self.assertEqual(item["like_count"], 10)
        self.assertEqual(item["share_count"], 1)
        self.assertEqual(item["collect_count"], 3)
        self.assertEqual(item["cover_url"], "https://example.com/b.jpg")
        self.assertEqual(item["status"], "已发布")

    def test_sort_by_create_time(self):
        items = parse_tencent_list_payload(SAMPLE, limit=2)
        self.assertEqual([i["item_id"] for i in items], ["newest", "mid"])

    def test_merge_by_object_id(self):
        short = {
            "errCode": 0,
            "data": {
                "list": [
                    {"objectId": "newest", "readCount": 200, "likeCount": 20},
                ]
            },
        }
        merged = merge_intercepted_payloads([SAMPLE, short])
        newest = next(x for x in merged if x["objectId"] == "newest")
        self.assertEqual(newest["readCount"], 200)
        self.assertEqual(newest["likeCount"], 20)
        self.assertEqual(newest["objectDesc"]["description"], "最新")


if __name__ == "__main__":
    unittest.main()
