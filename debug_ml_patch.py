import sys
from pathlib import Path
root = Path('app').resolve() / 'app'
if str(root) not in sys.path:
    sys.path.insert(0, str(root))
import app.ml_service as ml
import importlib
print('module name', ml.__name__)
print('module file', getattr(ml, '__file__', None))
print('module repr', repr(ml))
print('call_gemini', ml.call_gemini)
print('globals call_gemini', ml.__dict__['call_gemini'])
print('provider fn', ml.get_provider_callables()[0][1])
from unittest.mock import patch
with patch.object(ml, 'call_gemini') as mock_gemini:
    mock_gemini.return_value = '{"food":"pasta carbonara","weight_g":300,"confidence":0.95,"ingredients":[{"name":"pasta","type":"carb"},{"name":"bacon","type":"protein"}]}'
    print('patched call_gemini', ml.call_gemini)
    print('provider after patch', ml.get_provider_callables()[0][1])
    print('invoke', ml.get_provider_callables()[0][1]('prompt', 'path'))
    print('provider callable globals', ml.get_provider_callables()[0][1].__globals__.get('call_gemini'))
    print('all app.ml_service modules', [name for name in sys.modules if name.endswith('app.ml_service')])
    print('same object with app.app.ml_service', sys.modules['app.ml_service'] is sys.modules['app.app.ml_service'])
    from PIL import Image
    import tempfile
    import os
    tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
    tmp.close()
    img = Image.new('RGB', (100, 100), color='red')
    img.save(tmp.name)
    try:
        result = ml.analyze_image_sync(tmp.name)
        print('analyze_image_sync result', result)
    finally:
        os.unlink(tmp.name)
