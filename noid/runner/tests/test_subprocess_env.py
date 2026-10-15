from noid_runner.runner import _subprocess_env


def test_secrets_are_not_forwarded(monkeypatch):
    for name in ('SECRET_KEY', 'DATABASE_URL', 'PROCESSING_API_KEY',
                 'GROQ_API_KEY', 'POSTGRES_PASSWORD', 'HF_TOKEN'):
        monkeypatch.setenv(name, 'x')
    env = _subprocess_env()
    for name in ('SECRET_KEY', 'DATABASE_URL', 'PROCESSING_API_KEY',
                 'GROQ_API_KEY', 'POSTGRES_PASSWORD', 'HF_TOKEN'):
        assert name not in env


def test_regular_vars_are_forwarded(monkeypatch):
    monkeypatch.setenv('NOID_NAMESPACES', '/tmp/ns.yaml')
    monkeypatch.setenv('OLLAMA_HOST', 'http://host.docker.internal:11434')
    env = _subprocess_env({'EXTRA': '1'})
    assert env['NOID_NAMESPACES'] == '/tmp/ns.yaml'
    assert env['OLLAMA_HOST'] == 'http://host.docker.internal:11434'
    assert env['EXTRA'] == '1'
    assert 'PATH' in env


def test_passthrough_readmits_a_named_secret(monkeypatch):
    monkeypatch.setenv('HF_TOKEN', 'hf_x')
    monkeypatch.setenv('GROQ_API_KEY', 'gsk_x')
    monkeypatch.setenv('NOID_SUBPROCESS_ENV_PASSTHROUGH', 'HF_TOKEN')
    env = _subprocess_env()
    assert env['HF_TOKEN'] == 'hf_x'
    assert 'GROQ_API_KEY' not in env
