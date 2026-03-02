import unittest

from newsbot.llm import NoOpContentProcessor, OpenAIContentProcessor


class NoOpContentProcessorTests(unittest.TestCase):
    def test_prepare_adds_source_url(self):
        processor = NoOpContentProcessor()
        post = processor.prepare('Hello world', 'https://t.me/a/1')

        self.assertIn('Источник: https://t.me/a/1', post.body)
        self.assertEqual('Новость из отслеживаемого канала', post.title)

    def test_prepare_truncates_long_text(self):
        processor = NoOpContentProcessor()
        post = processor.prepare('x' * 1000, None)

        self.assertTrue(post.body.endswith('...'))
        self.assertLessEqual(len(post.body), 903)


class OpenAIContentProcessorParsingTests(unittest.TestCase):
    def test_parse_payload_plain_json(self):
        payload = OpenAIContentProcessor._parse_payload('{"title":"A","body":"B"}')
        self.assertEqual(payload['title'], 'A')
        self.assertEqual(payload['body'], 'B')

    def test_parse_payload_markdown_fence(self):
        payload = OpenAIContentProcessor._parse_payload('```json\n{"title":"A","body":"B"}\n```')
        self.assertEqual(payload['title'], 'A')

    def test_parse_payload_with_surrounding_text(self):
        payload = OpenAIContentProcessor._parse_payload(
            'Вот итог:\n{"title":"A","body":"B"}\nСпасибо!'
        )
        self.assertEqual(payload['body'], 'B')


if __name__ == '__main__':
    unittest.main()
