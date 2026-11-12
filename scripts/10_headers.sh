T=$(cat ~/.gh_token | tr -d '\r\n'); U=https://api.github.com/repos/upscayl/upscayl/releases/latest; O=data/headers_experiment.txt; : > $O
h(){ grep -iE '^(HTTP/|x-ratelimit-(limit|remaining|used|resource)|etag|cache-control|age|access-control-allow-origin|x-github-request-id|last-modified|vary)' | tr -d '\r'; }
echo "## E1 unauthenticated, plain (Origin: https://example.org)" >> $O; curl -s -D - -o /dev/null -H "Origin: https://example.org" $U | h >> $O
ET=$(curl -s -D - -o /dev/null $U | tr -d '\r' | grep -i '^etag' | cut -d' ' -f2-)
echo "## E2 unauthenticated conditional (If-None-Match) -> expect 304, compare remaining before/after" >> $O
curl -s -D - -o /dev/null https://api.github.com/rate_limit | h | grep -i remaining | sed 's/^/before: /' >> $O
curl -s -D - -o /dev/null -H "If-None-Match: $ET" $U | h >> $O
curl -s -D - -o /dev/null https://api.github.com/rate_limit | h | grep -i remaining | sed 's/^/after : /' >> $O
echo "## E3 authenticated plain" >> $O; curl -s -D - -o /dev/null -H "Authorization: Bearer $T" $U | h >> $O
ETA=$(curl -s -D - -o /dev/null -H "Authorization: Bearer $T" $U | tr -d '\r' | grep -i '^etag' | cut -d' ' -f2-)
echo "## E4 authenticated conditional" >> $O
curl -s -D - -o /dev/null -H "Authorization: Bearer $T" https://api.github.com/rate_limit | h | grep -i remaining | sed 's/^/before: /' >> $O
curl -s -D - -o /dev/null -H "Authorization: Bearer $T" -H "If-None-Match: $ETA" $U | h >> $O
curl -s -D - -o /dev/null -H "Authorization: Bearer $T" https://api.github.com/rate_limit | h | grep -i remaining | sed 's/^/after : /' >> $O
echo "## E5 CORS preflight from browser origin (OPTIONS)" >> $O; curl -s -D - -o /dev/null -X OPTIONS -H "Origin: https://example.org" -H "Access-Control-Request-Method: GET" -H "Access-Control-Request-Headers: if-none-match" $U | tr -d '\r' | grep -iE '^(HTTP/|access-control)' >> $O
echo "## E6 github.com/<o>/<r>/releases/latest/download/<name> (no API, no rate limit?) HEAD" >> $O
curl -s -I https://github.com/upscayl/upscayl/releases/latest/download/nonexistent.zip | tr -d '\r' | grep -iE '^(HTTP/|location|x-ratelimit|access-control)' >> $O
echo "## E7 releases.atom (public feed, no API quota)" >> $O; curl -s -D - -o /dev/null https://github.com/upscayl/upscayl/releases.atom | h >> $O
echo "## E8 raw.githubusercontent.com CORS (for a static catalog hosted on GitHub Pages/raw)" >> $O; curl -s -D - -o /dev/null https://raw.githubusercontent.com/upscayl/upscayl/main/README.md | tr -d '\r' | grep -iE '^(HTTP/|access-control|cache-control|x-ratelimit)' >> $O
cat $O
