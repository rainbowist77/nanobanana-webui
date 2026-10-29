import base64
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import app


PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class ConfiguredTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(dir=app.ROOT)
        self.addCleanup(directory.cleanup)
        self.config_path = Path(directory.name) / 'config.json'
        self.config = {'endpoint': 'https://example.com/custom/generations', 'api_key': 'test-key', 'model': 'custom-model'}
        self.save_config()
        config_patch = patch.object(app, 'CONFIG_PATH', self.config_path)
        config_patch.start()
        self.addCleanup(config_patch.stop)

    def save_config(self):
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8')


class GenerationTests(ConfiguredTest):

    def test_base64_saved_and_payload_matches_example(self):
        response = io.BytesIO(json.dumps({'data': [{'b64_json': base64.b64encode(PNG).decode()}]}).encode())
        with tempfile.TemporaryDirectory(dir=app.ROOT) as directory:
            with patch.object(app, 'OUTPUTS', Path(directory)), patch.object(app, 'urlopen', return_value=response) as remote:
                filename = app.generate_image('橘猫', '1024x1024')
                self.assertEqual((Path(directory) / filename).read_bytes(), PNG)
                request = remote.call_args.args[0]
                self.assertEqual(request.full_url, self.config['endpoint'])
                self.assertEqual(json.loads(request.data), {'model': 'custom-model', 'size': '1024x1024', 'prompt': '橘猫'})
                self.assertEqual(request.get_header('Authorization'), 'Bearer test-key')

    def test_missing_key_does_not_call_api(self):
        self.config['api_key'] = ''
        self.save_config()
        with patch.object(app, 'urlopen') as remote:
            with self.assertRaises(app.GenerationError):
                app.generate_image('cat', '1024x1024')
            remote.assert_not_called()

    def test_missing_model_does_not_call_api(self):
        for model in ('', '   '):
            self.config['model'] = model
            self.save_config()
            with self.subTest(model=model), patch.object(app, 'urlopen') as remote:
                with self.assertRaisesRegex(app.GenerationError, 'model'):
                    app.generate_image('cat', '1024x1024')
                remote.assert_not_called()

    def test_url_download_does_not_forward_key(self):
        metadata = io.BytesIO(b'{"data":[{"url":"https://example.com/image.png"}]}')
        picture = io.BytesIO(PNG)
        picture.geturl = lambda: 'https://example.com/image.png'
        with tempfile.TemporaryDirectory(dir=app.ROOT) as directory:
            with patch.object(app, 'OUTPUTS', Path(directory)), patch.object(app, 'urlopen', side_effect=[metadata, picture]) as remote:
                filename = app.generate_image('cat', '1024x1024')
                self.assertEqual((Path(directory) / filename).read_bytes(), PNG)
                self.assertIsNone(remote.call_args_list[1].args[0].get_header('Authorization'))

    def test_api_auth_error_is_readable(self):
        with patch.object(app, 'urlopen', side_effect=HTTPError(self.config['endpoint'], 401, 'Unauthorized', {}, None)):
            with self.assertRaisesRegex(app.GenerationError, 'API Key'):
                app.generate_image('cat', '1024x1024')


class ConfigTests(ConfiguredTest):
    def test_missing_and_invalid_json(self):
        self.config_path.unlink()
        with self.assertRaises(app.GenerationError):
            app.load_config()
        for text in ('{', '[]', '{"api_key": 123}', '\ufeff{}'):
            self.config_path.write_text(text, encoding='utf-8')
            with self.subTest(text=text), self.assertRaises(app.GenerationError):
                app.load_config()

    def test_endpoint_validation(self):
        for endpoint in ('', 'ftp://example.com', 'https://', 'https://example.com:bad', 'https://user:pass@example.com'):
            self.config['endpoint'] = endpoint
            self.save_config()
            with self.subTest(endpoint=endpoint), self.assertRaises(app.GenerationError):
                app.load_config()

    def test_reload_and_utf8_bom(self):
        self.assertEqual(app.load_config()['model'], 'custom-model')
        self.config['model'] = 'updated-model'
        self.config_path.write_text(json.dumps(self.config), encoding='utf-8-sig')
        self.assertEqual(app.load_config()['model'], 'updated-model')


class WebTests(ConfiguredTest):
    @classmethod
    def setUpClass(cls):
        cls.server = app.ThreadingHTTPServer(('127.0.0.1', 0), app.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_home_and_script(self):
        for route in ('/', '/app.js'):
            with urlopen(self.url + route) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())

    def test_status_requires_config_and_does_not_expose_key(self):
        for model, configured in [('', False), ('   ', False), ('custom-model', True)]:
            self.config['model'] = model
            self.save_config()
            with self.subTest(model=model):
                with urlopen(self.url + '/api/status') as response:
                    data = json.load(response)
                self.assertEqual(data['configured'], configured)
                self.assertNotIn('test-key', json.dumps(data))
                self.assertNotIn('api_key', data)

    def test_config_file_is_not_served(self):
        with self.assertRaises(HTTPError) as error:
            urlopen(self.url + '/config.json')
        self.assertEqual(error.exception.code, 404)

    def test_invalid_prompt_and_cross_origin_do_not_generate(self):
        with patch.object(app, 'generate_image') as generate:
            for origin, status in [(self.url, 400), ('https://example.com', 403)]:
                request = Request(self.url + '/api/generate', data=b'{"prompt":" "}', headers={'Origin': origin, 'Content-Type': 'application/json'})
                with self.assertRaises(HTTPError) as error:
                    urlopen(request)
                self.assertEqual(error.exception.code, status)
            generate.assert_not_called()

    def test_generation_route(self):
        with patch.object(app, 'generate_image', return_value='a' * 32 + '.png') as generate:
            request = Request(self.url + '/api/generate', data=json.dumps({'prompt': 'cat', 'size': '1024x1024'}).encode(), headers={'Origin': self.url, 'Content-Type': 'application/json'})
            with urlopen(request) as response:
                data = json.load(response)
                self.assertEqual(data['download_url'], '/download/' + 'a' * 32 + '.png')
            generate.assert_called_once_with('cat', '1024x1024')


if __name__ == '__main__':
    unittest.main()
