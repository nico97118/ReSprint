import pytest

from resprint.frontend.utils.jira_markup import render_jira_markup


def test_render_jira_markup_formats_links_emphasis_and_tables() -> None:
    html = render_jira_markup(
        "[Spec|https://jira.example.test/spec] *important* <script>\n"
        "||Colonne||Lien||\n"
        "|Valeur|[Doc|https://jira.example.test/doc]|"
    )

    assert '<a href="https://jira.example.test/spec">Spec</a>' in html
    assert "<strong>important</strong>" in html
    assert "&lt;script&gt;" in html
    assert '<table class="issue-comment-table">' in html
    assert "<th>Colonne</th>" in html
    assert "<td>Valeur</td>" in html
    assert '<a href="https://jira.example.test/doc">Doc</a>' in html


def test_render_jira_markup_formats_code_in_table_cells() -> None:
    html = render_jira_markup(
        "|message|{code:HTML}<p>A|B</p>{code}|\n"
        "|message|{code:HTML} message code{code}|\n"
        "|message|{code: HTML} message code spaced{code}|\n"
        "|Message| {code:HTML} message {code}|"
    )

    assert "&lt;p&gt;A|B&lt;/p&gt;" in html
    assert ">message code</code>" in html
    assert ">message code spaced</code>" in html
    assert "<td>Message</td>" in html
    assert ">message</code>" in html


def test_render_jira_markup_formats_standalone_code_block() -> None:
    html = render_jira_markup("{code:html}<div>bloc</div>{code}")

    assert "issue-comment-code-block" in html
    assert "&lt;div&gt;bloc&lt;/div&gt;" in html


def test_render_jira_markup_formats_git_changeset_comment() -> None:
    html = render_jira_markup(
        "2026-05-21 11:55 - GIT SNS: Changeset "
        "[7e5e0a5a|https://url.test.com] "
        ": "
        "|*Branch*|*master* | |Repository |repo_test | "
        "|Message |{code:HTML}\n"
        "ABC-1234 [TEST] FIX\n"
        "{code}| "
        "Content : {code:HTML}\n"
        "tests/file.yml | 45 +++\n"
        "1 file changed\n"
        "{code}"
    )

    assert '<a href="https://url.test.com">7e5e0a5a</a>' in html
    assert "<strong>Branch</strong>" in html
    assert "<strong>master</strong>" in html
    assert "repo_test" in html
    assert "ABC-1234 [TEST] FIX" in html
    assert "tests/file.yml | 45 +++" in html
    assert "1 file changed" in html


def test_multiline_code_preserves_newlines_escapes_html_and_resumes_text():
    html = render_jira_markup(
        "Before\n{code:python}\n<script>alert(1)</script>\nA | B\n{code} after\nEnd"
    )
    assert "&lt;script&gt;alert(1)&lt;/script&gt;\nA | B" in html
    assert "issue-comment-code-block" in html
    assert "after" in html and "End" in html
    assert "<script>" not in html


def test_unclosed_code_block_preserves_content_without_interpreting_markup():
    html = render_jira_markup("{code}\n*not bold*\n<img src=x onerror=alert(1)>")
    assert "*not bold*" in html
    assert "<strong>" not in html
    assert "&lt;img" in html
    assert "</pre>" in html


@pytest.mark.parametrize(
    "body",
    [
        "<script>alert(1)</script>",
        '<img src=x onerror="alert(1)">',
        "[click|javascript:alert(1)]",
        "[click](data:text/html,<script>alert(1)</script>)",
        '[<img src=x>|https://example.test/?q="onmouseover="alert(1)]',
        "|cell|<svg onload=alert(1)>|",
        "{code}<script>alert(1)</script>{code}",
    ],
)
def test_untrusted_comments_never_create_executable_markup(body):
    from html.parser import HTMLParser
    from urllib.parse import urlsplit

    class Tags(HTMLParser):
        def handle_starttag(self, tag, attrs):
            assert tag not in {"script", "img", "svg", "iframe"}
            for name, value in attrs:
                assert not name.lower().startswith("on")
                if name == "href":
                    assert urlsplit(value).scheme in {"http", "https"}

    Tags().feed(render_jira_markup(body))
