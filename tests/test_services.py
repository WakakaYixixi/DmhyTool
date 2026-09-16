import unittest

from app.services.dmhy import DMHYError
from app.services.magnet import normalize_detail_resource, parse_magnet_html
from app.services.search import parse_search_html


SEARCH_HTML = """
<table id="topic_list"><tbody><tr>
  <td>2026/09/16 12:34 <span>2026/09/16 12:34</span></td>
  <td>动画</td>
  <td class="title">
    <span class="tag"><a href="/topics/list/team_id/123">测试字幕组</a></span>
    <a href="/topics/view/724804_example.html">测试标题</a>
  </td>
  <td><a class="arrow-magnet" href="magnet:?xt=urn:btih:ignored">下载</a></td>
  <td>1.2GB</td>
</tr></tbody></table>
"""


class SearchParserTests(unittest.TestCase):
    def test_parses_structured_result_without_magnet(self) -> None:
        results = parse_search_html(SEARCH_HTML)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "724804")
        self.assertEqual(results[0]["title"], "测试标题")
        self.assertEqual(results[0]["published_at"], "2026/09/16 12:34")
        self.assertEqual(results[0]["group"], "测试字幕组")
        self.assertEqual(results[0]["size"], "1.2GB")
        self.assertNotIn("magnet", results[0])

    def test_empty_page_is_empty_result(self) -> None:
        self.assertEqual(parse_search_html("<html><body>没有结果</body></html>"), [])

    def test_changed_structure_is_reported(self) -> None:
        with self.assertRaises(DMHYError):
            parse_search_html('<a href="/topics/view/123_changed.html">item</a>')


class MagnetTests(unittest.TestCase):
    def test_prefers_primary_magnet(self) -> None:
        html = """
        <a href="magnet:?xt=urn:btih:secondary">secondary</a>
        <a class="magnet" href="magnet:?xt=urn:btih:primary&amp;tr=x">primary</a>
        """
        self.assertEqual(
            parse_magnet_html(html), "magnet:?xt=urn:btih:primary&tr=x"
        )

    def test_accepts_id_and_dmhy_detail_url(self) -> None:
        self.assertEqual(
            normalize_detail_resource("724804"),
            ("724804", "https://share.dmhy.org/topics/view/724804_.html"),
        )
        resource_id, url = normalize_detail_resource(
            "https://share.dmhy.org/topics/view/724804_example.html"
        )
        self.assertEqual(resource_id, "724804")
        self.assertEqual(
            url, "https://share.dmhy.org/topics/view/724804_example.html"
        )

    def test_rejects_ssrf_and_invalid_paths(self) -> None:
        invalid = [
            "https://example.com/topics/view/724804_example.html",
            "http://127.0.0.1/topics/view/724804_example.html",
            "https://share.dmhy.org/admin",
            "https://share.dmhy.org:8080/topics/view/724804_example.html",
            "file:///etc/passwd",
        ]
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_detail_resource(value)


if __name__ == "__main__":
    unittest.main()
