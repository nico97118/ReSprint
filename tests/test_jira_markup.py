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
