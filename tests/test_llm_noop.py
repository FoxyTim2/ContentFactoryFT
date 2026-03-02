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

    def test_validate_payload_rejects_additional_fields(self):
        with self.assertRaises(ValueError):
            OpenAIContentProcessor._validate_and_trim_payload(
                {'title': 'A', 'body': 'B', 'extra': 'C'}
            )

    def test_validate_payload_trims_lengths(self):
        title = 't' * 100
        body = 'b' * 1300
        validated_title, validated_body = OpenAIContentProcessor._validate_and_trim_payload(
            {'title': title, 'body': body}
        )

        self.assertLessEqual(len(validated_title), OpenAIContentProcessor.MAX_TITLE_LENGTH)
        self.assertTrue(validated_title.endswith('...'))
        self.assertLessEqual(len(validated_body), OpenAIContentProcessor.MAX_BODY_LENGTH)
        self.assertTrue(validated_body.endswith('...'))

    def test_append_source_line_adds_source_at_end(self):
        result = OpenAIContentProcessor._append_source_line(
            'Краткий текст',
            'https://t.me/a/1',
        )
        self.assertTrue(result.endswith('Источник: https://t.me/a/1'))

    def test_append_source_line_does_not_duplicate_source(self):
        body = 'Краткий текст\n\nИсточник: https://t.me/a/1'
        result = OpenAIContentProcessor._append_source_line(body, 'https://t.me/a/1')
        self.assertEqual(result, body)


class PostStructureTests(unittest.TestCase):
    def test_single_source_post_to_single_published_post_structure(self):
        prepared_title = 'Заголовок'
        prepared_body = OpenAIContentProcessor._append_source_line(
            'Тело поста',
            'https://t.me/a/1',
        )

        final_text = f'{prepared_title}\n\n{prepared_body}'

        self.assertEqual(final_text.count('Заголовок'), 1)
        self.assertEqual(final_text.count('Источник:'), 1)
        self.assertEqual(final_text, 'Заголовок\n\nТело поста\n\nИсточник: https://t.me/a/1')


if __name__ == '__main__':
    unittest.main()
