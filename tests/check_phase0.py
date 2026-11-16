"""Comprehensive Phase 0 health check script."""
import sys
import json
import tempfile
import pathlib
import os

results = []

# 1. All 8 pip packages
try:
    import streamlit, pydantic, sklearn, pandas, pytest, dotenv, faiss
    from google import genai
    results.append(('All 8 pip packages import', 'PASS', ''))
except Exception as e:
    results.append(('All 8 pip packages import', 'FAIL', str(e)))

# 2. All stub modules importable
modules = [
    'app', 'app.main',
    'core', 'core.parser', 'core.categoriser', 'core.budget_engine', 'core.savings', 'core.nudges',
    'scam', 'scam.rules', 'scam.classifier', 'scam.llm_judge', 'scam.verifier', 'scam.pipeline',
    'rag', 'rag.ingest', 'rag.retrieve',
    'llm', 'llm.prompts', 'llm.schemas',
    'eval',
]
for m in modules:
    try:
        __import__(m)
        results.append((f'import {m}', 'PASS', ''))
    except Exception as e:
        results.append((f'import {m}', 'FAIL', str(e)))

# 3. Adapter exception classes
try:
    from llm.adapter import (
        LLMAdapter, LLMAdapterError, LLMConfigurationError,
        LLMTimeoutError, LLMRateLimitError, LLMSchemaValidationError
    )
    results.append(('Adapter classes importable', 'PASS', ''))
except Exception as e:
    results.append(('Adapter classes importable', 'FAIL', str(e)))

# 4. Pydantic schema
try:
    from llm.schemas import SmokeTestResult
    s = SmokeTestResult(status='ok', message='test')
    assert s.status == 'ok'
    results.append(('SmokeTestResult schema valid', 'PASS', ''))
except Exception as e:
    results.append(('SmokeTestResult schema valid', 'FAIL', str(e)))

# 5. Mock adapter instantiation
try:
    from llm.adapter import LLMAdapter
    a = LLMAdapter(provider='mock', cache_enabled=False)
    results.append(('Mock adapter instantiation', 'PASS', ''))
except Exception as e:
    results.append(('Mock adapter instantiation', 'FAIL', str(e)))

# 6. Mock generate_structured returns typed Pydantic model
try:
    from llm.schemas import SmokeTestResult
    result = a.generate_structured('ping', SmokeTestResult)
    assert isinstance(result, SmokeTestResult)
    results.append(('Mock generate_structured typed result', 'PASS', ''))
except Exception as e:
    results.append(('Mock generate_structured typed result', 'FAIL', str(e)))

# 7. Missing model raises LLMConfigurationError
try:
    from llm.adapter import LLMConfigurationError
    raised = False
    try:
        LLMAdapter(provider='gemini', model='', api_key='dummy')
    except LLMConfigurationError:
        raised = True
    assert raised
    results.append(('Missing model -> LLMConfigurationError', 'PASS', ''))
except Exception as e:
    results.append(('Missing model -> LLMConfigurationError', 'FAIL', str(e)))

# 8. Invalid provider raises LLMConfigurationError
try:
    raised = False
    try:
        LLMAdapter(provider='openai', model='x', api_key='dummy')
    except LLMConfigurationError:
        raised = True
    assert raised
    results.append(('Invalid provider -> LLMConfigurationError', 'PASS', ''))
except Exception as e:
    results.append(('Invalid provider -> LLMConfigurationError', 'FAIL', str(e)))

# 9. Cache directory auto-created
try:
    with tempfile.TemporaryDirectory() as td:
        cache_dir = pathlib.Path(td) / 'test_cache'
        a2 = LLMAdapter(provider='mock', cache_enabled=True, cache_dir=cache_dir)
        assert cache_dir.exists()
    results.append(('Cache directory auto-created', 'PASS', ''))
except Exception as e:
    results.append(('Cache directory auto-created', 'FAIL', str(e)))

# 10. Disk cache write and read-back
try:
    from llm.schemas import SmokeTestResult
    with tempfile.TemporaryDirectory() as td:
        a3 = LLMAdapter(provider='mock', cache_enabled=True, cache_dir=pathlib.Path(td))
        r1 = a3.generate_structured('cache-test', SmokeTestResult)
        cached_files = list(pathlib.Path(td).glob('*.json'))
        assert len(cached_files) == 1, f"Expected 1 cache file, got {len(cached_files)}"
        r2 = a3.generate_structured('cache-test', SmokeTestResult)
        assert r1.status == r2.status
    results.append(('Disk cache write and read-back', 'PASS', ''))
except Exception as e:
    results.append(('Disk cache write and read-back', 'FAIL', str(e)))

# 11. Cache clear
try:
    from llm.schemas import SmokeTestResult
    with tempfile.TemporaryDirectory() as td:
        a4 = LLMAdapter(provider='mock', cache_enabled=True, cache_dir=pathlib.Path(td))
        a4.generate_structured('x', SmokeTestResult)
        cleared = a4.clear_cache()
        assert cleared == 1
    results.append(('Cache clear removes files', 'PASS', ''))
except Exception as e:
    results.append(('Cache clear removes files', 'FAIL', str(e)))

# 12. Canned mock response
try:
    from llm.schemas import SmokeTestResult
    a5 = LLMAdapter(provider='mock', cache_enabled=False)
    a5.register_mock_response('SmokeTestResult', {'status': 'live', 'message': 'canned'})
    r = a5.generate_structured('anything', SmokeTestResult)
    assert r.status == 'live'
    results.append(('Canned mock response registration', 'PASS', ''))
except Exception as e:
    results.append(('Canned mock response registration', 'FAIL', str(e)))

# 13. Markdown fence stripping
try:
    from llm.adapter import _clean_json_text
    raw = "```json\n{\"a\": 1}\n```"
    cleaned = _clean_json_text(raw)
    parsed = json.loads(cleaned)
    assert parsed['a'] == 1
    results.append(('Markdown fence stripping', 'PASS', ''))
except Exception as e:
    results.append(('Markdown fence stripping', 'FAIL', str(e)))

# 14. .env.example has all required vars
try:
    content = open('.env.example').read()
    required = ['LLM_PROVIDER', 'LLM_API_KEY', 'LLM_MODEL', 'EMBEDDING_MODEL',
                'LLM_TEMPERATURE', 'LLM_TIMEOUT_SECONDS', 'LLM_MAX_RETRIES',
                'LLM_CACHE_ENABLED', 'LLM_CACHE_DIR']
    missing = [v for v in required if v not in content]
    if missing:
        results.append(('.env.example completeness', 'FAIL', f'Missing: {missing}'))
    else:
        results.append(('.env.example completeness', 'PASS', ''))
except Exception as e:
    results.append(('.env.example completeness', 'FAIL', str(e)))

# 15. .gitignore correctness
try:
    content = open('.gitignore').read()
    checks = ['.venv/', '.env', '__pycache__/', '.cache/', '.pytest_cache/']
    missing = [c for c in checks if c not in content]
    if missing:
        results.append(('.gitignore completeness', 'FAIL', f'Missing: {missing}'))
    else:
        results.append(('.gitignore completeness', 'PASS', ''))
except Exception as e:
    results.append(('.gitignore completeness', 'FAIL', str(e)))

# 16. requirements.txt all 8 packages pinned
try:
    content = open('requirements.txt').read()
    pkgs = ['streamlit==', 'pydantic==', 'scikit-learn==', 'pandas==',
            'pytest==', 'python-dotenv==', 'google-genai==', 'faiss-cpu==']
    missing = [p for p in pkgs if p not in content]
    if missing:
        results.append(('requirements.txt pinned', 'FAIL', f'Missing: {missing}'))
    else:
        results.append(('requirements.txt pinned', 'PASS', ''))
except Exception as e:
    results.append(('requirements.txt pinned', 'FAIL', str(e)))

# 17. smoke_test.py syntax valid
try:
    src = pathlib.Path('smoke_test.py').read_text()
    compile(src, 'smoke_test.py', 'exec')
    results.append(('smoke_test.py syntax valid', 'PASS', ''))
except Exception as e:
    results.append(('smoke_test.py syntax valid', 'FAIL', str(e)))

# 18. Smoke test end-to-end with mock (no API key needed)
try:
    from llm.schemas import SmokeTestResult
    a_smoke = LLMAdapter(provider='mock', cache_enabled=False)
    r = a_smoke.generate_structured('smoke test ping', SmokeTestResult)
    assert isinstance(r, SmokeTestResult)
    assert r.status is not None
    assert r.message is not None
    results.append(('Smoke test end-to-end (mock)', 'PASS', ''))
except Exception as e:
    results.append(('Smoke test end-to-end (mock)', 'FAIL', str(e)))

# 19. .env exists and is not empty (without reading values)
try:
    p = pathlib.Path('.env')
    assert p.exists(), ".env file not found"
    assert p.stat().st_size > 0, ".env file is empty"
    results.append(('.env file exists and non-empty', 'PASS', ''))
except Exception as e:
    results.append(('.env file exists and non-empty', 'FAIL', str(e)))

# 20. SPEC.md present and non-empty
try:
    p = pathlib.Path('SPEC.md')
    assert p.exists() and p.stat().st_size > 1000
    results.append(('SPEC.md present and non-trivial', 'PASS', ''))
except Exception as e:
    results.append(('SPEC.md present and non-trivial', 'FAIL', str(e)))

# Print report
print()
print(f"{'CHECK':<50} STATUS  DETAIL")
print('=' * 80)
passed = failed = 0
for name, status, detail in results:
    icon = 'PASS' if status == 'PASS' else 'FAIL'
    if status == 'PASS':
        passed += 1
    else:
        failed += 1
    detail_str = f'  <- {detail}' if detail else ''
    print(f"[{icon}] {name:<48}{detail_str}")
print('=' * 80)
print(f"RESULT: {passed}/{len(results)} passed   {'ALL CHECKS PASSED' if failed == 0 else f'{failed} FAILED'}")
sys.exit(0 if failed == 0 else 1)
