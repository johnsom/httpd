import pytest

from pyhttpd.conf import HttpdConf


class TestEncoding:

    EXP_AH10244_ERRS = 0

    @pytest.fixture(autouse=True, scope='class')
    def _class_scope(self, env):
        conf = HttpdConf(env, extras={
            'base': f"""
        <Directory "{env.gen_dir}">
            AllowOverride None
            Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
            Require all granted
        </Directory>
        """,
            f"test2.{env.http_tld}": "AllowEncodedSlashes on",
            f"cgi.{env.http_tld}": f"ScriptAlias /cgi-bin/ {env.gen_dir}",
        })
        conf.add_vhost_test1()
        conf.add_vhost_test2()
        conf.add_vhost_cgi()
        conf.install()
        assert env.apache_restart() == 0

    # check handling of url encodings that are accepted
    @pytest.mark.parametrize("path", [
        "/006/006.css",
        "/%30%30%36/%30%30%36.css",
        "/nothing/../006/006.css",
        "/nothing/./../006/006.css",
        "/nothing/%2e%2e/006/006.css",
        "/nothing/%2e/%2e%2e/006/006.css",
        "/nothing/%2e/%2e%2e/006/006%2ecss",
    ])
    def test_core_001_01(self, env, path):
        url = env.mkurl("https", "test1", path)
        r = env.curl_get(url)
        assert r.response["status"] == 200

    # check handling of / normalization
    @pytest.mark.parametrize("path", [
        "/006//006.css",
        "/006//////////006.css",
        "/006////.//////006.css",
        "/006////%2e//////006.css",
        "/006////%2e//////006%2ecss",
        "/006/../006/006.css",
        "/006/%2e%2e/006/006.css",
    ])
    def test_core_001_03(self, env, path):
        url = env.mkurl("https", "test1", path)
        r = env.curl_get(url)
        assert r.response["status"] == 200

    # check path traversals
    @pytest.mark.parametrize(["path", "status"], [
        ["/../echo.py", 400],
        ["/nothing/../../echo.py", 400],
        ["/cgi-bin/../../echo.py", 400],
        ["/nothing/%2e%2e/%2e%2e/echo.py", 400],
        ["/cgi-bin/%2e%2e/%2e%2e/echo.py", 400],
        ["/nothing/%%32%65%%32%65/echo.py", 400],
        ["/cgi-bin/%%32%65%%32%65/echo.py", 400],
        ["/nothing/%%32%65%%32%65/%%32%65%%32%65/h2_env.py", 400],
        ["/cgi-bin/%%32%65%%32%65/%%32%65%%32%65/h2_env.py", 400],
        ["/nothing/%25%32%65%25%32%65/echo.py", 404],
        ["/cgi-bin/%25%32%65%25%32%65/echo.py", 404],
        ["/nothing/%25%32%65%25%32%65/%25%32%65%25%32%65/h2_env.py", 404],
        ["/cgi-bin/%25%32%65%25%32%65/%25%32%65%25%32%65/h2_env.py", 404],
    ])
    def test_core_001_04(self, env, path, status):
        url = env.mkurl("https", "cgi", path)
        r = env.curl_get(url)
        assert r.response["status"] == status
        if status == 400:
            TestEncoding.EXP_AH10244_ERRS += 1
            # the log will have a core:err about invalid URI path

    # check handling of %2f url encodings that are not decoded by default
    @pytest.mark.parametrize(["host", "path", "status"], [
        ["test1", "/006%2f006.css", 404],
        ["test2", "/006%2f006.css", 200],
        ["test2", "/x%252f.test", 200],
        ["test2", "/10%25abnormal.txt", 200],
    ])
    def test_core_001_20(self, env, host, path, status):
        url = env.mkurl("https", host, path)
        r = env.curl_get(url)
        assert r.response["status"] == status
